from .io_nodes       import (LoadVolumeNode, SaveVolumeNode, SaveDataNode,
                              SampleDataNode, NewMarkupNode,
                              VolumesNode, MarkupsNode)
from .filter_nodes   import ThresholdNode, GaussianSmoothNode, MedianFilterNode
from .simple_filter_node import SimpleFilterNode
from .segment_nodes  import (SegmentationNode, SegmentEditorNode,
                              SegmentationsNode)
from .segment_ops_nodes import (SegmentFilterNode, SurfaceModelNode,
                                 SegmentStatisticsNode, MaskVolumeNode,
                                 LabelMapToSegmentationNode)
from .register_nodes import RegistrationNode, ApplyTransformNode, TransformsNode
from .resample_nodes import ResampleVolumeNode, VolumeMathNode
from .viz_nodes      import VolumeRenderingNode, ModelsNode
from .layout_node    import LayoutNode
from .process_nodes  import CropVolumeNode

# Master registry: every class here appears in the Tab search popup
ALL_NODE_CLASSES = [
    # I/O
    SampleDataNode,
    LoadVolumeNode,
    SaveVolumeNode,
    SaveDataNode,
    NewMarkupNode,
    VolumesNode,
    MarkupsNode,
    # Filters / processing
    ThresholdNode,
    GaussianSmoothNode,
    MedianFilterNode,
    SimpleFilterNode,
    VolumeMathNode,
    CropVolumeNode,
    # Segmentation
    SegmentationNode,
    SegmentEditorNode,
    SegmentationsNode,
    SegmentFilterNode,
    MaskVolumeNode,
    LabelMapToSegmentationNode,
    SurfaceModelNode,
    # Measurement
    SegmentStatisticsNode,
    # Registration / transforms
    RegistrationNode,
    ApplyTransformNode,
    ResampleVolumeNode,
    TransformsNode,
    # Visualization
    VolumeRenderingNode,
    ModelsNode,
    # Layout
    LayoutNode,
]

# Stable type-id → class map used by graph (de)serialisation. The id is
# NODE_TYPE if a class sets it, else the class name. If a class is ever
# renamed, set NODE_TYPE to the old name so saved graphs keep loading.
NODE_TYPE_REGISTRY = {
    (c.NODE_TYPE or c.__name__): c for c in ALL_NODE_CLASSES
}

__all__ = [c.__name__ for c in ALL_NODE_CLASSES] + [
    'ALL_NODE_CLASSES', 'NODE_TYPE_REGISTRY']
