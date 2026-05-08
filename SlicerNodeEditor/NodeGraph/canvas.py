"""
NodeEditorCanvas - wraps NodeGraphQt's NodeGraph with Slicer-specific node
registration and context menu actions.
"""

from NodeGraphQt import NodeGraph
from Nodes.io_nodes import LoadVolumeNode, SaveVolumeNode
from Nodes.filter_nodes import ThresholdNode, GaussianSmoothNode
from Nodes.segment_nodes import SegmentationNode
from Nodes.register_nodes import RegistrationNode
from Nodes.viz_nodes import VolumeRenderingNode


_ALL_NODE_TYPES = [
    LoadVolumeNode,
    SaveVolumeNode,
    ThresholdNode,
    GaussianSmoothNode,
    SegmentationNode,
    RegistrationNode,
    VolumeRenderingNode,
]


class NodeEditorCanvas:
    """Initializes the NodeGraphQt graph and registers all Slicer node types."""

    def __init__(self):
        self.graph = NodeGraph()
        self._registerNodes()
        self._configureAppearance()
        self._buildContextMenu()

    def _registerNodes(self):
        for node_class in _ALL_NODE_TYPES:
            self.graph.register_node(node_class)

    def _configureAppearance(self):
        self.graph.set_background_color(18, 18, 18)
        self.graph.set_grid_mode(1)  # dots grid like Nuke

    def _buildContextMenu(self):
        """Add right-click 'Add Node' sub-menus by category."""
        menu = self.graph.get_context_menu("graph")

        categories = {
            "I/O": [LoadVolumeNode, SaveVolumeNode],
            "Filters": [ThresholdNode, GaussianSmoothNode],
            "Segmentation": [SegmentationNode],
            "Registration": [RegistrationNode],
            "Visualization": [VolumeRenderingNode],
        }

        for category, node_classes in categories.items():
            sub = menu.add_menu(category)
            for cls in node_classes:
                # NodeGraphQt uses the node type string "identifier.ClassName"
                sub.add_command(
                    cls.NODE_NAME,
                    func=lambda c=cls: self.graph.create_node(c.__identifier__ + "." + c.NODE_NAME),
                )

    def get_native_window(self):
        """Return the underlying QWidget for embedding in Slicer's Qt layout."""
        return self.graph.viewer()
