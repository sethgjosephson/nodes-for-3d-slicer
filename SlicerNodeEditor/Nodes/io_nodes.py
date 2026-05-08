"""I/O nodes: loading and saving data from disk to/from the MRML scene."""

import slicer
from NodeGraph.node import SlicerBaseNode


class LoadVolumeNode(SlicerBaseNode):
    __identifier__ = "slicer.io"
    NODE_NAME = "Load Volume"
    NODE_COLOR = (60, 90, 130)

    INPUT_PORTS = []
    OUTPUT_PORTS = [("volume_out", "Volume")]

    def __init__(self):
        super().__init__()
        self.add_text_input("file_path", "File Path")

    def execute(self, inputs: dict) -> dict:
        path = self.get_property("file_path")
        if not path:
            raise ValueError("Load Volume: no file path specified.")
        node = slicer.util.loadVolume(path)
        return {"volume_out": node}


class SaveVolumeNode(SlicerBaseNode):
    __identifier__ = "slicer.io"
    NODE_NAME = "Save Volume"
    NODE_COLOR = (60, 90, 130)

    INPUT_PORTS = [("volume_in", "Volume")]
    OUTPUT_PORTS = []

    def __init__(self):
        super().__init__()
        self.add_text_input("file_path", "File Path")

    def execute(self, inputs: dict) -> dict:
        node = inputs.get("volume_in")
        path = self.get_property("file_path")
        if node is None:
            raise ValueError("Save Volume: no input volume connected.")
        if not path:
            raise ValueError("Save Volume: no output path specified.")
        slicer.util.saveNode(node, path)
        return {}
