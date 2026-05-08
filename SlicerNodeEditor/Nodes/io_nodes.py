"""I/O nodes: load and save volumes from/to disk."""

import slicer
from .base_node import SlicerBaseNode, VOLUME


class LoadVolumeNode(SlicerBaseNode):
    NODE_NAME    = "Load Volume"
    CATEGORY     = "I/O"

    INPUT_PORTS  = []
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'file_path', 'label': 'File Path', 'type': 'str', 'default': ''},
    ]

    def execute(self, inputs):
        path = self.get_property('file_path')
        if not path:
            raise ValueError("Load Volume: no file path specified.")
        node = slicer.util.loadVolume(path)
        return {'volume_out': node}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            _route_volume_to_slices(node)


class SaveVolumeNode(SlicerBaseNode):
    NODE_NAME    = "Save Volume"
    CATEGORY     = "I/O"

    INPUT_PORTS  = [("volume_in", "Volume", VOLUME)]
    OUTPUT_PORTS = []

    PROPERTIES = [
        {'name': 'file_path', 'label': 'Output Path', 'type': 'str', 'default': ''},
    ]

    def execute(self, inputs):
        node = inputs.get('volume_in')
        path = self.get_property('file_path')
        if node is None:
            raise ValueError("Save Volume: no input volume connected.")
        if not path:
            raise ValueError("Save Volume: no output path specified.")
        slicer.util.saveNode(node, path)
        return {}


# ---------------------------------------------------------------------------
# Shared routing helper
# ---------------------------------------------------------------------------

def _route_volume_to_slices(node):
    """Show a volume in the conventional 3-slice + 3D Slicer layout."""
    lm = slicer.app.layoutManager()
    lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView)
    nid = node.GetID()
    for color in ('Red', 'Yellow', 'Green'):
        cn = slicer.mrmlScene.GetNodeByID(
            f'vtkMRMLSliceCompositeNode{color}')
        if cn:
            cn.SetBackgroundVolumeID(nid)
    slicer.util.resetSliceViews()
