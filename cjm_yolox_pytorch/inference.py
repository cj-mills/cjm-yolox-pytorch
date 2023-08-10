# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/04_inference.ipynb.

# %% auto 0
__all__ = ['YOLOXInferenceWrapper']

# %% ../nbs/04_inference.ipynb 4
import os
from typing import Any, Type, List, Optional, Callable, Tuple
from functools import partial

from pathlib import Path

# %% ../nbs/04_inference.ipynb 5
import torch
import torch.nn as nn

import torch.nn.init as init

# %% ../nbs/04_inference.ipynb 6
from .model import build_model, NORM_STATS
from .utils import generate_output_grids

# %% ../nbs/04_inference.ipynb 8
class YOLOXInferenceWrapper(nn.Module):
    """
    This is a wrapper for the YOLOX <https://arxiv.org/abs/2107.08430> object detection model.
    The class handles preprocessing of the input, postprocessing of the model output, and calculation of bounding boxes and their probabilities.
    """

    def __init__(self, 
                 model:nn.Module, # The YOLOX model.
                 normalize_mean:torch.Tensor=torch.tensor([[[0.]]]*3)[None], # The mean values for normalization.
                 normalize_std:torch.Tensor=torch.tensor([[[1.]]]*3)[None], # The standard deviation values for normalization.
                 strides:Optional[List[int]]=[8, 16, 32], # The strides for the model.
                 scale_inp:bool=False, # Whether to scale the input by dividing by 255.
                 channels_first:bool=False, # Whether the input tensor has channels first.
                 run_box_and_prob_calculation:bool=True # Whether to calculate the bounding boxes and their probabilities.
                ):
        """
        Constructor for the YOLOXInferenceWrapper class.
        """
        super().__init__()
        self.model = model
        self.register_buffer("normalize_mean", normalize_mean)
        self.register_buffer("normalize_std", normalize_std)
        self.scale_inp = scale_inp
        self.channels_first = channels_first
        self.register_buffer("strides", torch.tensor(strides))
        self.run_box_and_prob_calculation = run_box_and_prob_calculation

    def preprocess_input(self, x):
        """
        Preprocess the input for the model.

        Parameters:
        x (torch.Tensor): The input tensor.

        Returns:
        torch.Tensor: The preprocessed input tensor.
        """
        # Scale the input if required
        if self.scale_inp:
            x = x / 255.0

        # Permute the dimensions of the input to bring the channels to the front if required
        if self.channels_first:
            x = x.permute(0, 3, 1, 2)

        # Normalize the input
        x = (x - self.normalize_mean) / self.normalize_std
        return x
        
    def process_output(self, model_output):
        """
        Postprocess the output of the model.

        Parameters:
        model_output (tuple): The output of the model.

        Returns:
        torch.Tensor: The postprocessed output tensor.
        """
        cls_scores, bbox_preds, objectness = model_output
        
        stride_flats = []
        # Iterate over the output strides
        for i in range(self.strides.shape[0]):
            cls = torch.sigmoid(cls_scores[i])  # Apply sigmoid to the class scores
            bbox = bbox_preds[i]  # Get the bounding box predictions
            obj = torch.sigmoid(objectness[i])  # Apply sigmoid to the objectness scores
            cat = torch.cat((bbox, obj, cls), dim=1)  # Concatenate the bounding boxes, objectness, and class scores
            flat = torch.flatten(cat, start_dim=2)  # Flatten the tensor from the second dimension
            stride_flats.append(flat)

        # Concatenate all the flattened tensors
        full_cat = torch.cat(stride_flats, dim=2)
        full_cat_out = full_cat.permute(0, 2, 1)  # Permute the dimensions of the tensor
        return full_cat_out

    def calculate_boxes_and_probs(self, model_output, output_grids):
        """
        Calculate the bounding boxes and their probabilities.

        Parameters:
        model_output (torch.Tensor): The output of the model.
        output_grids (torch.Tensor): The output grids.

        Returns:
        torch.Tensor: The tensor containing the bounding box coordinates, class labels, and maximum probabilities.
        """
        # Calculate the bounding box coordinates
        box_centroids = (model_output[..., :2] + output_grids[..., :2]) * output_grids[..., 2:]
        box_sizes = torch.exp(model_output[..., 2:4]) * output_grids[..., 2:]
        
        x0, y0 = [t.squeeze(dim=2) for t in torch.split(box_centroids - box_sizes / 2, 1, dim=2)]
        w, h = [t.squeeze(dim=2) for t in torch.split(box_sizes, 1, dim=2)]

        # Calculate the probabilities for each class
        box_objectness = model_output[..., 4]
        box_cls_scores = model_output[..., 5:]
        box_probs = box_objectness.unsqueeze(-1) * box_cls_scores

        # Get the maximum probability and corresponding class for each proposal
        max_probs, labels = torch.max(box_probs, dim=-1)

        return torch.stack([x0, y0, w, h, labels.float(), max_probs], dim=-1)

    def forward(self, x):
        """
        The forward method for the YOLOXInferenceWrapper class.

        Parameters:
        x (torch.Tensor): The input tensor.

        Returns:
        torch.Tensor: The output tensor.
        """
        
        input_dims = x.shape[-2:]
                
        # Preprocess the input
        x = self.preprocess_input(x)
        # Pass the input through the model
        x = self.model(x)
        # Postprocess the model output
        x = self.process_output(x)
        
        if self.run_box_and_prob_calculation:
            # Generate output grids
            output_grids = generate_output_grids(*input_dims, self.strides).to(x.device)
            # Calculate the bounding boxes and their probabilities
            x = self.calculate_boxes_and_probs(x, output_grids)
        
        return x
