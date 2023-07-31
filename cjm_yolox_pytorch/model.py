# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_model.ipynb.

# %% auto 0
__all__ = ['MODEL_TYPES', 'CSP_DARKNET_CFGS', 'PAFPN_CFGS', 'HEAD_CFGS', 'HUGGINGFACE_CKPT_URL', 'PRETRAINED_URLS', 'NORM_CFG',
           'NORM_STATS', 'MODEL_CFGS', 'ConvModule', 'DarknetBottleneck', 'CSPLayer', 'Focus', 'SPPBottleneck',
           'CSPDarknet', 'YOLOXPAFPN', 'YOLOXHead', 'YOLOX', 'init_head', 'build_model']

# %% ../nbs/00_model.ipynb 4
import os
from typing import Any, Type, List, Optional, Callable, Tuple
from functools import partial

from pathlib import Path

# %% ../nbs/00_model.ipynb 5
import torch
import torch.nn as nn

import torch.nn.init as init

# %% ../nbs/00_model.ipynb 6
from .utils import multi_apply

# %% ../nbs/00_model.ipynb 8
MODEL_TYPES = ['yolox_tiny', 'yolox_s', 'yolox_m', 'yolox_l', 'yolox_x']

CSP_DARKNET_CFGS = {
    MODEL_TYPES[0]:dict(deepen_factor=0.33, widen_factor=0.375),
    MODEL_TYPES[1]:dict(deepen_factor=0.33, widen_factor=0.5),
    MODEL_TYPES[2]:dict(deepen_factor=0.67, widen_factor=0.75),
    MODEL_TYPES[3]:dict(deepen_factor=1.0, widen_factor=1.0),
    MODEL_TYPES[4]:dict(deepen_factor=1.33, widen_factor=1.25)
}

PAFPN_CFGS = {
    MODEL_TYPES[0]:dict(in_channels=[96, 192, 384], out_channels=96, num_csp_blocks=1),
    MODEL_TYPES[1]:dict(in_channels=[128, 256, 512], out_channels=128, num_csp_blocks=1),
    MODEL_TYPES[2]:dict(in_channels=[192, 384, 768], out_channels=192, num_csp_blocks=2),
    MODEL_TYPES[3]:dict(in_channels=[256, 512, 1024], out_channels=256, num_csp_blocks=3),
    MODEL_TYPES[4]:dict(in_channels=[320, 640, 1280], out_channels=320, num_csp_blocks=4),
}

HEAD_CFGS = {
    MODEL_TYPES[0]:dict(in_channels=96,feat_channels=96),
    MODEL_TYPES[1]:dict(in_channels=128,feat_channels=128),
    MODEL_TYPES[2]:dict(in_channels=192, feat_channels=192),
    MODEL_TYPES[3]:dict(in_channels=256, feat_channels=256),
    MODEL_TYPES[4]:dict(in_channels=320, feat_channels=320),
}

HUGGINGFACE_CKPT_URL = 'https://huggingface.co/cj-mills/yolox-coco-baseline-pytorch/resolve/main'

# PRETRAINED_URLS = {
#     MODEL_TYPES[0]:f'{HUGGINGFACE_CKPT_URL}/yolox_tiny.pth',
#     MODEL_TYPES[1]:f'{HUGGINGFACE_CKPT_URL}/yolox_s.pth',
#     MODEL_TYPES[2]:f'{HUGGINGFACE_CKPT_URL}/yolox_m.pth',
#     MODEL_TYPES[3]:f'{HUGGINGFACE_CKPT_URL}/yolox_l.pth',
#     MODEL_TYPES[4]:f'{HUGGINGFACE_CKPT_URL}/yolox_x.pth',
# }

PRETRAINED_URLS = {
    MODEL_TYPES[0]:None,
    MODEL_TYPES[1]:None,
    MODEL_TYPES[2]:None,
    MODEL_TYPES[3]:None,
    MODEL_TYPES[4]:None,
}

NORM_CFG = dict(momentum=0.03, eps=0.001)

NORM_STATS = {
    MODEL_TYPES[0]:dict(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    MODEL_TYPES[1]:dict(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    MODEL_TYPES[2]:dict(mean=(0.5, 0.5, 0.5), std=(1.0, 1.0, 1.0)),
    MODEL_TYPES[3]:dict(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    MODEL_TYPES[4]:dict(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
}

MODEL_CFGS = {model_type: {**CSP_DARKNET_CFGS[model_type], 
                            **{'neck_'+k: v for k, v in PAFPN_CFGS[model_type].items()}, 
                            **{'head_'+k: v for k, v in HEAD_CFGS[model_type].items()}} 
               for model_type in MODEL_TYPES}

# %% ../nbs/00_model.ipynb 11
class ConvModule(nn.Module):
    """
    Configurable block used for Convolution2d-Normalization-Activation blocks.
    
    #### Pseudocode
    Function forward(input x):
    
        1. Pass the input (x) through the convolutional layer and store the result back to x.
        2. Pass the output from the convolutional layer (now stored in x) through the batch normalization layer and store the result back to x.
        3. Apply the activation function to the output of the batch normalization layer (x) and return the result.

    """

    def __init__(self, 
                 in_channels: int,  # Number of channels in the input image
                 out_channels: int, # Number of channels produced by the convolution
                 kernel_size: int,  # Size of the convolving kernel
                 stride: int = 1,   # Stride of the convolution.
                 padding: int = 0,  # Zero-padding added to both sides of the input.
                 bias: bool = True, # If set to False, the layer will not learn an additive bias.
                 eps: float = 1e-05,    # A value added to the denominator for numerical stability in BatchNorm2d.
                 momentum: float = 0.1, # The value used for the running_mean and running_var computation in BatchNorm2d.
                 affine: bool = True,   # If set to True, this module has learnable affine parameters.
                 track_running_stats: bool = True, # If set to True, this module tracks the running mean and variance.
                 activation_function: Type[nn.Module] = nn.SiLU # The activation function to be applied after batch normalization.
                ):
        
        super(ConvModule, self).__init__()

        # Convolutional layer
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding, bias=bias)
        # Batch normalization layer
        self.bn = nn.BatchNorm2d(out_channels, eps=eps, momentum=momentum, affine=affine, track_running_stats=track_running_stats)
        # Activation function
        self.activate = activation_function()
        
        init.kaiming_normal_(self.conv.weight.data, mode='fan_out', nonlinearity='relu')

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        
        # Pass input through convolutional layer
        x = self.conv(x)
        # Pass output from convolutional layer through batch normalization
        x = self.bn(x)
        # Apply activation function and return result
        return self.activate(x)

# %% ../nbs/00_model.ipynb 14
class DarknetBottleneck(nn.Module):
    """
    Basic Darknet bottleneck block used in Darknet.
    
    This class represents a basic bottleneck block used in Darknet, which consists of two convolutional layers with a possible identity shortcut.
    
    Based on OpenMMLab's implementation in the mmdetection library:
    
     - [OpenMMLab's Implementation](https://github.com/open-mmlab/mmdetection/blob/d64e719172335fa3d7a757a2a3636bd19e9efb62/mmdet/models/utils/csp_layer.py#L8)
    """
    
    def __init__(self, 
                 in_channels: int, # The number of input channels to the block.
                 out_channels: int, # The number of output channels from the block.
                 eps: float = 0.001, # A value added to the denominator for numerical stability in the ConvModule's BatchNorm layer.
                 momentum: float = 0.03, # The value used for the running_mean and running_var computation in the ConvModule's BatchNorm layer.
                 affine: bool = True, # A flag that when set to True, gives the ConvModule's BatchNorm layer learnable affine parameters.
                 track_running_stats: bool = True, # If True, the ConvModule's BatchNorm layer will track the running mean and variance.
                 add_identity: bool = True # If True, add an identity shortcut (also known as skip connection) to the output.
                ) -> None:
        super(DarknetBottleneck, self).__init__()

        self.add_identity = add_identity

        # The first conv layer reduces the dimensionality with a 1x1 kernel, 
        # and the second conv layer restores it with a 3x3 kernel.
        self.conv1 = ConvModule(in_channels, out_channels, kernel_size=1, stride=1, padding=0, 
                                bias=False, eps=eps, momentum=momentum, affine=affine, 
                                track_running_stats=track_running_stats)
        self.conv2 = ConvModule(out_channels, out_channels, kernel_size=3, stride=1, padding=1, 
                                bias=False, eps=eps, momentum=momentum, affine=affine, 
                                track_running_stats=track_running_stats)
        
        # If add_identity is True and in_channels do not match out_channels, 
        # introduce a conv layer on the identity shortcut to match the dimensions.
        # If not, use nn.Identity() for a cleaner forward method.
        if self.add_identity and in_channels != out_channels:
            self.identity_conv = ConvModule(in_channels, out_channels, kernel_size=1, stride=1, padding=0, 
                                            bias=False, eps=eps, momentum=momentum, affine=affine, 
                                            track_running_stats=track_running_stats)
        else:
            self.identity_conv = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        out = self.conv2(self.conv1(x))
        
        # If add_identity is True, add the transformed (if necessary) identity to the output
        if self.add_identity:
            out += self.identity_conv(identity)

        return out

# %% ../nbs/00_model.ipynb 17
class CSPLayer(nn.Module):
    """
    Cross Stage Partial Layer (CSPLayer).
    
    This layer consists of a series of convolutions, blocks of transformations, and a final convolution. 
    The inputs are processed via two paths: a main path with blocks and a shortcut path. The results from 
    both paths are concatenated and further processed before returning the final output.

    The blocks are instances of the DarknetBottleneck class which perform additional transformations.
    
    Based on OpenMMLab's implementation in the mmdetection library:
    
    - [OpenMMLab's Implementation](https://github.com/open-mmlab/mmdetection/blob/d64e719172335fa3d7a757a2a3636bd19e9efb62/mmdet/models/)
    """
    def __init__(self, 
                 in_channels: int, # Number of input channels.
                 out_channels: int, # Number of output channels.
                 num_blocks: int, # Number of blocks in the bottleneck.
                 kernel_size: int = 1, # Size of the convolving kernel.
                 stride: int = 1, # Stride of the convolution.
                 padding: int = 0, # Zero-padding added to both sides of the input.
                 eps: float = 0.001, # A value added to the denominator for numerical stability.
                 momentum: float = 0.03, # The value used for the running_mean and running_var computation.
                 affine: bool = True, # A flag that when set to True, gives the layer learnable affine parameters.
                 track_running_stats: bool = True, # Whether or not to track the running mean and variance during training.
                 add_identity: bool = True # Whether or not to add an identity shortcut connection if the input and output are the same size.
                ) -> None:
        
        super().__init__()

        hidden_channels = out_channels // 2

        self.main_conv = ConvModule(in_channels, hidden_channels, kernel_size, stride, padding, 
                                    bias=False, eps=eps, momentum=momentum, affine=affine, 
                                    track_running_stats=track_running_stats)

        self.short_conv = ConvModule(in_channels, hidden_channels, kernel_size, stride, padding, 
                                     bias=False, eps=eps, momentum=momentum, affine=affine, 
                                     track_running_stats=track_running_stats)

        self.final_conv = ConvModule(2 * hidden_channels, out_channels, kernel_size, stride, padding, 
                                     bias=False, eps=eps, momentum=momentum, affine=affine, 
                                     track_running_stats=track_running_stats)
        
        self.blocks = nn.ModuleList([DarknetBottleneck(hidden_channels, hidden_channels, eps, momentum, affine, track_running_stats, add_identity) for _ in range(num_blocks)])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        
        main_path = self.main_conv(x)
        for block in self.blocks:
            main_path = block(main_path)

        shortcut_path = self.short_conv(x)

        return self.final_conv(torch.cat((main_path, shortcut_path), dim=1))

# %% ../nbs/00_model.ipynb 20
class Focus(nn.Module):
    """
    Focus width and height information into channel space.
    
    Based on OpenMMLab's implementation in the mmdetection library:
    
    - [OpenMMLab's Implementation](https://github.com/open-mmlab/mmdetection/blob/d64e719172335fa3d7a757a2a3636bd19e9efb62/mmdet/models/backbones/csp_darknet.py#L14)
    """
    
    def __init__(self,
                 in_channels: int, # Number of input channels.
                 out_channels: int, # Number of output channels.
                 kernel_size: int = 1, # Size of the convolving kernel.
                 stride: int = 1, # Stride of the convolution.
                 bias: bool = False, # If set to False, the layer will not learn an additive bias.
                 eps: float = 0.001, #  A value added to the denominator for numerical stability in the ConvModule's BatchNorm layer.
                 momentum: float = 0.03, # The value used for the running_mean and running_var computation in the ConvModule's BatchNorm layer.
                 affine: bool = True, # A flag that when set to True, gives the ConvModule's BatchNorm layer learnable affine parameters.
                 track_running_stats: bool = True # Whether or not to track the running mean and variance during training.
                ):
        
        super(Focus, self).__init__()
        self.conv = ConvModule(
            in_channels * 4,
            out_channels,
            kernel_size,
            stride,
            padding=(kernel_size - 1) // 2,
            bias=bias,
            eps=eps,
            momentum=momentum,
            affine=affine,
            track_running_stats=track_running_stats)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
                
        # Split the input tensor into 4 patches
        patch_top_left = x[..., ::2, ::2]   # Top left patch
        patch_top_right = x[..., ::2, 1::2]  # Top right patch
        patch_bot_left = x[..., 1::2, ::2]  # Bottom left patch
        patch_bot_right = x[..., 1::2, 1::2]  # Bottom right patch
        
        # Concatenate the patches along the channel dimension in order respecting the spatial locality
        x = torch.cat(
            (
                patch_top_left,
                patch_top_right,
                patch_bot_left,
                patch_bot_right,
            ),
            dim=1,
        )
        return self.conv(x)

# %% ../nbs/00_model.ipynb 23
class SPPBottleneck(nn.Module):
    """
    Spatial Pyramid Pooling layer used in YOLOv3-SPP
    
    Based on OpenMMLab's implementation in the mmdetection library:
    
    - [OpenMMLab's Implementation](https://github.com/open-mmlab/mmdetection/blob/d64e719172335fa3d7a757a2a3636bd19e9efb62/mmdet/models/backbones/csp_darknet.py#L67)
    """
    def __init__(self, 
                 in_channels: int, # The number of input channels.
                 out_channels: int, # The number of output channels.
                 pool_sizes: List[int] = [5, 9, 13], # The sizes of the pooling areas.
                 eps: float = 0.001, # A value added to the denominator for numerical stability in the BatchNorm layer.
                 momentum: float = 0.03, #  The value used for the running_mean and running_var computation in the BatchNorm layer.
                 affine: bool = True, # A flag that when set to True, gives the BatchNorm layer learnable affine parameters.
                 track_running_stats: bool = True # Whether to keep track of running mean and variance in BatchNorm.
                ) -> None:
        
        super(SPPBottleneck, self).__init__()

        hidden_channels = in_channels // 2

        self.conv1 = ConvModule(in_channels, hidden_channels, kernel_size=1, stride=1, padding=0, 
                                bias=False, eps=eps, momentum=momentum, affine=affine, 
                                track_running_stats=track_running_stats)

        self.pooling_layers = nn.ModuleList([nn.MaxPool2d(kernel_size=ps, stride=1, padding=ps//2) for ps in pool_sizes])

        self.conv2 = ConvModule(hidden_channels * (len(pool_sizes) + 1), out_channels, kernel_size=1, stride=1, padding=0, 
                                bias=False, eps=eps, momentum=momentum, affine=affine, 
                                track_running_stats=track_running_stats)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
                
        x = self.conv1(x)

        pooling_results = [x]
        for pooling in self.pooling_layers:
            pooling_results.append(pooling(x))

        x = torch.cat(pooling_results, dim=1)

        return self.conv2(x)

# %% ../nbs/00_model.ipynb 26
class CSPDarknet(nn.Module):
    """
    The `CSPDarknet` class implements a CSPDarknet backbone, a convolutional neural network (CNN) used in various image recognition tasks. The CSPDarknet backbone forms an integral part of the YOLOX object detection model.
    
    Based on OpenMMLab's implementation in the mmdetection library:
    
    - [OpenMMLab's Implementation](https://github.com/open-mmlab/mmdetection/blob/d64e719172335fa3d7a757a2a3636bd19e9efb62/mmdet/models/backbones/csp_darknet.py#L124)
    """

    # Architecture settings for P5 and P6
    ARCH_SETTINGS = {
        'P5': [[64, 128, 3, True, False], [128, 256, 9, True, False],
               [256, 512, 9, True, False], [512, 1024, 3, False, True]],
        'P6': [[64, 128, 3, True, False], [128, 256, 9, True, False],
               [256, 512, 9, True, False], [512, 768, 3, True, False],
               [768, 1024, 3, False, True]]
    }

    def __init__(self,
                 arch='P5', # Architecture configuration, 'P5' or 'P6'.
                 deepen_factor=1.0, # Factor to adjust the number of channels in each layer.
                 widen_factor=1.0, # Factor to adjust the number of blocks in CSP layer.
                 out_indices=(2, 3, 4), # Indices of the stages to output.
                 spp_kernal_sizes=(5, 9, 13), # Sizes of the pooling operations in the Spatial Pyramid Pooling.
                 momentum=0.03, # Momentum for the moving average in batch normalization.
                 eps=0.001 # Epsilon for batch normalization to avoid numerical instability.
                ):
        
        super().__init__()

        if not set(out_indices).issubset(range(len(self.ARCH_SETTINGS[arch]) + 1)):
            raise ValueError("out_indices are out of range")

        self.out_indices = out_indices
        # Building the initial layer of the model
        self.stem = Focus(
            3,
            int(self.ARCH_SETTINGS[arch][0][0] * widen_factor),
            kernel_size=3,
            stride=1
            )
        self.layers = ['stem']
        # Building the stages of the model
        self._build_stages(arch, deepen_factor, widen_factor, spp_kernal_sizes, momentum, eps)

    def _build_stages(self, arch, deepen_factor, widen_factor, spp_kernal_sizes, momentum, eps):
        """
        Build the stages of the CSPDarknet model.

        Args:
            arch (str): Architecture type, 'P5' or 'P6'.
            deepen_factor (float): Factor to adjust the depth of the model.
            widen_factor (float): Factor to adjust the width of the model.
            spp_kernal_sizes (tuple): Sizes of the pooling operations in the Spatial Pyramid Pooling.
            momentum (float): Momentum for the moving average in batch normalization.
            eps (float): Epsilon for batch normalization to avoid numerical instability.
        """

        # For each stage configuration in the architecture settings
        for i, (in_c, out_c, num_blocks, add_identity, use_spp) in enumerate(self.ARCH_SETTINGS[arch]):
            # Adjust the channel size based on the widen factor
            in_c, out_c = int(in_c * widen_factor), int(out_c * widen_factor)
            # Adjust the number of blocks based on the deepen factor
            num_blocks = max(round(num_blocks * deepen_factor), 1)

            stage = []

            # Append ConvModule for the stage
            stage.append(ConvModule(in_c, 
                                    out_c, 3, 
                                    stride=2, 
                                    padding=1, 
                                    bias=False, 
                                    eps=eps, 
                                    momentum=momentum, 
                                    affine=True, 
                                    track_running_stats=True))

            # If use_spp is True, append a Spatial Pyramid Pooling layer
            if use_spp:
                stage.append(SPPBottleneck(out_c, out_c, pool_sizes=spp_kernal_sizes))

            # Append a Cross Stage Partial layer
            stage.append(CSPLayer(out_c, out_c, num_blocks=num_blocks, add_identity=add_identity))
            # Add the stage to the model as a sequential layer
            self.add_module(f'stage{i + 1}', nn.Sequential(*stage))
            self.layers.append(f'stage{i + 1}')

    def forward(self, x):
                
        outs = []
        # For each layer in the model
        for i, layer_name in enumerate(self.layers):
            # Get the layer by its name
            layer = getattr(self, layer_name)
            # Pass the input through the layer
            x = layer(x)
            # If the index is in out_indices, append the output to outs
            if i in self.out_indices:
                outs.append(x)
        return tuple(outs)

# %% ../nbs/00_model.ipynb 30
class YOLOXPAFPN(nn.Module):
    """
    Path Aggregation Feature Pyramid Network (PAFPN) used in YOLOX.
    
    In object detection tasks, this class merges the feature maps from different layers of the backbone network. It helps in aggregating multi-scale feature maps to enhance the detection of objects of various sizes.
    
    Based on OpenMMLab's implementation in the mmdetection library:
    
    - [OpenMMLab's Implementation](https://github.com/open-mmlab/mmdetection/blob/d64e719172335fa3d7a757a2a3636bd19e9efb62/mmdet/models/necks/yolox_pafpn.py#L14)
    """
    
    def __init__(self,
                 in_channels,
                 out_channels,
                 num_csp_blocks=3,
                 upsample_cfg=dict(scale_factor=2, mode='nearest'),
                 momentum=0.03,
                 eps=0.001):
        super(YOLOXPAFPN, self).__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.upsample = nn.Upsample(**upsample_cfg)

        # build top-down blocks, which includes reduce layers and CSP blocks
        self.reduce_layers = nn.ModuleList([
            ConvModule(
                in_channels[idx],
                in_channels[idx - 1],
                kernel_size=(1, 1),
                stride=(1, 1),
                padding=0,
                bias=False,
                momentum=momentum,
                eps=eps,
                affine=True,
                track_running_stats=True
            ) for idx in range(len(in_channels) - 1, 0, -1)
        ])
        self.top_down_blocks = nn.ModuleList([
            CSPLayer(
                in_channels[idx - 1] * 2,
                in_channels[idx - 1],
                num_blocks=num_csp_blocks,
                add_identity=False
            ) for idx in range(len(in_channels) - 1, 0, -1)
        ])

        # build bottom-up blocks, which includes downsampling layers and CSP blocks
        self.downsamples = nn.ModuleList([
            ConvModule(
                in_channels[idx],
                in_channels[idx],
                3,
                stride=2,
                padding=1,
                bias=False,
                momentum=momentum,
                eps=eps,
                affine=True,
                track_running_stats=True
            ) for idx in range(len(in_channels) - 1)
        ])
        self.bottom_up_blocks = nn.ModuleList([
            CSPLayer(
                in_channels[idx] * 2,
                in_channels[idx + 1],
                num_blocks=num_csp_blocks,
                add_identity=False
            ) for idx in range(len(in_channels) - 1)
        ])

        # build output convolutions for each level
        self.out_convs = nn.ModuleList([
            ConvModule(
                in_channels[i],
                out_channels,
                1,
                stride=(1, 1),
                padding=0,
                bias=False,
                momentum=momentum,
                eps=eps,
                affine=True,
                track_running_stats=True
            ) for i in range(len(in_channels))
        ])

    def forward(self, inputs):
        assert len(inputs) == len(self.in_channels)

        # top-down path
        inner_outs = self._top_down(inputs)

        # bottom-up path
        outs = self._bottom_up(inner_outs)

        # apply the output convolutions to the feature maps
        outs = [conv(out) for out, conv in zip(outs, self.out_convs)]

        return tuple(outs)

    def _top_down(self, inputs):
        inner_outs = [inputs[-1]]
        for idx, (reduce_layer, block) in enumerate(zip(self.reduce_layers, self.top_down_blocks)):
            feat_high = reduce_layer(inner_outs[0])
            inner_outs[0] = feat_high
            upsample_feat = self.upsample(feat_high)
            inner_out = block(torch.cat([upsample_feat, inputs[len(inputs) - 2 - idx]], 1))
            inner_outs.insert(0, inner_out)
        return inner_outs

    def _bottom_up(self, inner_outs):
        outs = [inner_outs[0]]
        for idx, (downsample, block) in enumerate(zip(self.downsamples, self.bottom_up_blocks)):
            downsample_feat = downsample(outs[-1])
            out = block(torch.cat([downsample_feat, inner_outs[idx + 1]], 1))
            outs.append(out)
        return outs

# %% ../nbs/00_model.ipynb 33
class YOLOXHead(nn.Module):
    """
    The `YOLOXHead` class is a PyTorch module that implements the head of a YOLOX model <https://arxiv.org/abs/2107.08430>, used for bounding box prediction.
    
    The head takes as input feature maps at multiple scale levels (e.g., from a feature pyramid network) and outputs predicted class scores, bounding box coordinates, and objectness scores for each scale level.
    
    Based on OpenMMLab's implementation in the mmdetection library:
    
    - [OpenMMLab's Implementation](https://github.com/open-mmlab/mmdetection/blob/d64e719172335fa3d7a757a2a3636bd19e9efb62/mmdet/models/dense_heads/yolox_head.py#L20)
    """
    
    BBOX_DIM = 4
    OBJECTNESS_DIM = 1

    def __init__(self,
                 num_classes:int, # The number of target classes.
                 in_channels:int, # The number of input channels.
                 feat_channels=256, # The number of feature channels.
                 stacked_convs=2, # The number of convolution layers to stack.
                 strides=[8, 16, 32], # The stride of each scale level in the feature pyramid.
                 momentum=0.03, # The momentum for the moving average in batch normalization.
                 eps=0.001 # The epsilon to avoid division by zero in batch normalization.
                ):

        super().__init__()
        # Store various configurations as instance variables
        self.num_classes = num_classes
        self.cls_out_channels = num_classes
        self.in_channels = in_channels
        self.feat_channels = feat_channels
        self.stacked_convs = stacked_convs
        self.strides = strides
        self.momentum = momentum
        self.eps = eps
        
        # Initialize the layers of the model
        self._init_layers()

    def _init_layers(self):
        """
        Initialize layers for the head module, includes classification 
        convolutions, regression convolutions and prediction convolutions 
        for each scale level.
        """
        # Initialize multi-level lists for each type of layer
        self.multi_level_cls_convs = nn.ModuleList()
        self.multi_level_reg_convs = nn.ModuleList()
        self.multi_level_conv_cls = nn.ModuleList()
        self.multi_level_conv_reg = nn.ModuleList()
        self.multi_level_conv_obj = nn.ModuleList()
        
        # For each stride level, create layers and add them to their respective lists
        for _ in self.strides:
            self.multi_level_cls_convs.append(self._build_stacked_convs())
            self.multi_level_reg_convs.append(self._build_stacked_convs())
            conv_cls, conv_reg, conv_obj = self._build_predictor()
            self.multi_level_conv_cls.append(conv_cls)
            self.multi_level_conv_reg.append(conv_reg)
            self.multi_level_conv_obj.append(conv_obj)

    def _build_stacked_convs(self):
        """
        Build stacked convolution layers.
        """
        conv = ConvModule
        stacked_convs = []
        # Create a series of convolution layers
        for i in range(self.stacked_convs):
            chn = self.in_channels if i == 0 else self.feat_channels
            stacked_convs.append(
                conv(
                    chn,
                    self.feat_channels,
                    3,
                    stride=1,
                    padding=1,
                    momentum=self.momentum,
                    eps=self.eps,
                    affine=True, 
                    track_running_stats=True,
                    bias=False))
        # Return the layers as a sequential model
        return nn.Sequential(*stacked_convs)

    def _build_predictor(self):
        """
        Build predictor layers for classification, regression, and objectness.
        """
        # Create convolution layers for each type of prediction
        conv_cls = nn.Conv2d(self.feat_channels, self.cls_out_channels, 1)
        conv_reg = nn.Conv2d(self.feat_channels, self.BBOX_DIM, 1)
        conv_obj = nn.Conv2d(self.feat_channels, self.OBJECTNESS_DIM, 1)
        return conv_cls, conv_reg, conv_obj

    def forward_single(self, x, cls_convs, reg_convs, conv_cls, conv_reg, conv_obj):
        """
        Forward feature of a single scale level.
        """
        # Pass input through classification and regression convolutions
        cls_feat = cls_convs(x)
        reg_feat = reg_convs(x)

        # Apply predictors to get scores and predictions
        cls_score = conv_cls(cls_feat)
        bbox_pred = conv_reg(reg_feat)
        objectness = conv_obj(reg_feat)

        return cls_score, bbox_pred, objectness

    def forward(self, feats):
        """
        Forward pass for the head.
        """
        # Apply the forward_single function to each scale level
        return multi_apply(self.forward_single, feats,
                           self.multi_level_cls_convs,
                           self.multi_level_reg_convs,
                           self.multi_level_conv_cls,
                           self.multi_level_conv_reg,
                           self.multi_level_conv_obj)

# %% ../nbs/00_model.ipynb 36
class YOLOX(nn.Module):
    """
    Implementation of `YOLOX: Exceeding YOLO Series in 2021`
    
    - <https://arxiv.org/abs/2107.08430>
    
    #### Pseudocode
    Function forward(input_tensor x):

    1. Pass x through the backbone module. The backbone module performs feature extraction from the input images. Store the output as 'x'.
    2. Pass the updated x through the neck module. The neck module performs feature aggregation of the extracted features. Update 'x' with the new output.
    3. Pass the updated x through the bbox_head module. The bbox_head module predicts bounding boxes for potential objects in the images using the aggregated features. Update 'x' with the new output.
    4. Return 'x' as the final output. The final 'x' represents the model's predictions for object locations within the input images.

    """
    def __init__(self, 
                 backbone:CSPDarknet, # Backbone module for feature extraction.
                 neck:YOLOXPAFPN, # Neck module for feature aggregation.
                 bbox_head:YOLOXHead): # Bbox head module for predicting bounding boxes.
        super(YOLOX, self).__init__()

        self.backbone = backbone
        self.neck = neck
        self.bbox_head = bbox_head

    def forward(self, x):
        # Forward through backbone
        x = self.backbone(x)

        # Forward through neck
        x = self.neck(x)

        # Forward through bbox_head
        x = self.bbox_head(x)

        return x

# %% ../nbs/00_model.ipynb 39
def init_head(head: YOLOXHead, # The YOLOX head to be initialized.
              num_classes: int # The number of classes in the dataset.
             ) -> None:
    """
    Initialize the `YOLOXHead` with appropriate class outputs and convolution layers.

    This function configures the output channels in the YOLOX head to match the
    number of classes in the dataset. It also initializes multiple level
    convolutional layers for each stride in the YOLOX head.
    """

    # Set the number of output channels in the head to be equal to the number of classes
    head.cls_out_channels = num_classes

    # Create a list of 2D convolutional layers, one for each stride in the head.
    # Each convolutional layer will have a number of output channels equal to the number of classes
    # and a kernel size of 1 (i.e., it will perform a 1x1 convolution).
    
    conv_layers = [nn.Conv2d(head.feat_channels, head.cls_out_channels, 1) for _ in head.strides]
    
    for conv in conv_layers:
        # Use Kaiming initialization to initialize the weights of the convolutional layers. 
        init.kaiming_normal_(conv.weight.data, mode='fan_out', nonlinearity='relu')
    
    head.multi_level_conv_cls = nn.ModuleList(conv_layers)

# %% ../nbs/00_model.ipynb 43
from cjm_psl_utils.core import download_file

# %% ../nbs/00_model.ipynb 44
def build_model(model_type:str, # Type of the model to be built.
                num_classes:int, # Number of classes for the model.
                pretrained:bool=True, # Whether to load pretrained weights.
                checkpoint_dir:str='./pretrained_checkpoints/' # Directory to store checkpoints.
               ) -> YOLOX: # The built YOLOX model.
    """
    Builds a YOLOX model based on the given parameters.
    """
    
    assert model_type in MODEL_TYPES, f"Invalid model_type. Expected one of: {MODEL_TYPES}, but got {model_type}"

    backbone_cfg = CSP_DARKNET_CFGS[model_type]
    neck_cfg = PAFPN_CFGS[model_type]
    head_cfg = HEAD_CFGS[model_type]
    
    backbone = CSPDarknet(**backbone_cfg)
    neck = YOLOXPAFPN(**neck_cfg)

    if pretrained and PRETRAINED_URLS[model_type] == None:
        print("The selected model type does not have a pretrained checkpoint. Initializing model with untrained weights.")
        pretrained = False
    
    try:
        if pretrained:
            url = PRETRAINED_URLS[model_type]
            checkpoint_path = os.path.join(checkpoint_dir, Path(url).name)
            download_file(url, checkpoint_dir)
            
            state_dict = torch.load(checkpoint_path)
            num_pretrained_classes = state_dict['bbox_head.multi_level_conv_cls.0.weight'].shape[0]
            
            head = YOLOXHead(num_classes=num_pretrained_classes, **head_cfg)
        else:
            head = YOLOXHead(num_classes=num_classes, **head_cfg)
        
        yolox = YOLOX(backbone, neck, head)
        
        if pretrained:
            yolox.load_state_dict(state_dict)
            init_head(head, num_classes)
            
    except Exception as e:
        print(f"Error occurred while building the model: {str(e)}")
        return None

    return yolox
