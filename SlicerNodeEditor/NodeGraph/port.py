"""
Port type constants used when declaring node ports.
These are passed as metadata so the executor can validate connections.
"""

VOLUME = "vtkMRMLScalarVolumeNode"
LABELMAP = "vtkMRMLLabelMapVolumeNode"
SEGMENTATION = "vtkMRMLSegmentationNode"
TRANSFORM = "vtkMRMLTransformNode"
MODEL = "vtkMRMLModelNode"
ANY = "any"
