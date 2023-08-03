# cjm-yolox-pytorch

<!-- WARNING: THIS FILE WAS AUTOGENERATED! DO NOT EDIT! -->

## Install

``` sh
pip install cjm_yolox_pytorch
```

## How to use

``` python
import torch
from cjm_yolox_pytorch.model import MODEL_TYPES, build_model
```

**Select model type**

``` python
model_type = MODEL_TYPES[0]
model_type
```

    'yolox_tiny'

**Build YOLOX model**

``` python
yolox = build_model(model_type, 19, pretrained=True)

test_inp = torch.randn(1, 3, 256, 256)

with torch.no_grad():
    cls_scores, bbox_preds, objectness = yolox(test_inp)
    
print(f"cls_scores: {[cls_score.shape for cls_score in cls_scores]}")
print(f"bbox_preds: {[bbox_pred.shape for bbox_pred in bbox_preds]}")
print(f"objectness: {[objectness.shape for objectness in objectness]}")
```

    The file ./pretrained_checkpoints/yolox_tiny.pth already exists and overwrite is set to False.
    Error occurred while building the model: Attempting to deserialize object on a CUDA device but torch.cuda.is_available() is False. If you are running on a CPU-only machine, please use torch.load with map_location=torch.device('cpu') to map your storages to the CPU.

    TypeError: 'NoneType' object is not callable
