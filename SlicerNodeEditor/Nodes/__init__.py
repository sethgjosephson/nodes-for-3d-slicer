from .io_nodes      import LoadVolumeNode, SaveVolumeNode
from .filter_nodes  import ThresholdNode, GaussianSmoothNode, MedianFilterNode
from .segment_nodes import SegmentationNode
from .register_nodes import RegistrationNode, ApplyTransformNode
from .viz_nodes     import VolumeRenderingNode
from .layout_node   import LayoutNode

# Master registry — every class here appears in the Tab search popup
ALL_NODE_CLASSES = [
    LoadVolumeNode,
    SaveVolumeNode,
    ThresholdNode,
    GaussianSmoothNode,
    MedianFilterNode,
    SegmentationNode,
    RegistrationNode,
    ApplyTransformNode,
    VolumeRenderingNode,
    LayoutNode,
]

__all__ = [c.__name__ for c in ALL_NODE_CLASSES] + ['ALL_NODE_CLASSES']
