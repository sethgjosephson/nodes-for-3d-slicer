from .io_nodes       import (LoadVolumeNode, SaveVolumeNode, SampleDataNode,
                              VolumesNode, MarkupsNode)
from .filter_nodes   import ThresholdNode, GaussianSmoothNode, MedianFilterNode
from .segment_nodes  import (SegmentationNode, SegmentEditorNode,
                              SegmentationsNode)
from .register_nodes import RegistrationNode, ApplyTransformNode, TransformsNode
from .viz_nodes      import VolumeRenderingNode, ModelsNode
from .layout_node    import LayoutNode
from .process_nodes  import CropVolumeNode

# Master registry — every class here appears in the Tab search popup
ALL_NODE_CLASSES = [
    # I/O
    SampleDataNode,
    LoadVolumeNode,
    SaveVolumeNode,
    VolumesNode,
    MarkupsNode,
    # Filters / processing
    ThresholdNode,
    GaussianSmoothNode,
    MedianFilterNode,
    CropVolumeNode,
    # Segmentation
    SegmentationNode,
    SegmentEditorNode,
    SegmentationsNode,
    # Registration / transforms
    RegistrationNode,
    ApplyTransformNode,
    TransformsNode,
    # Visualization
    VolumeRenderingNode,
    ModelsNode,
    # Layout
    LayoutNode,
]

__all__ = [c.__name__ for c in ALL_NODE_CLASSES] + ['ALL_NODE_CLASSES']
