"""Segmentation nodes."""

import slicer
from NodeGraph.node import SlicerBaseNode


class SegmentationNode(SlicerBaseNode):
    __identifier__ = "slicer.segment"
    NODE_NAME = "Segmentation"
    NODE_COLOR = (130, 80, 130)

    INPUT_PORTS = [("volume_in", "Volume")]
    OUTPUT_PORTS = [("segmentation_out", "Segmentation")]

    def __init__(self):
        super().__init__()
        self.add_combo_menu("method", "Method", items=["Grow from Seeds", "Threshold", "Auto"])
        self.add_float_input("threshold", "Threshold", value=100.0)

    def execute(self, inputs: dict) -> dict:
        volume_node = inputs.get("volume_in")
        if volume_node is None:
            raise ValueError("Segmentation: no input volume connected.")

        seg_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        seg_node.SetName(f"{volume_node.GetName()}_seg")
        seg_node.CreateDefaultDisplayNodes()

        method = self.get_property("method")
        threshold = self.get_property("threshold")

        if method in ("Threshold", "Auto"):
            seg_node.GetSegmentation().AddEmptySegment("Segment_1")
            effect_params = {
                "InputVolume": volume_node,
                "OutputSegmentation": seg_node,
                "MinimumThreshold": threshold,
                "MaximumThreshold": 3000.0,
            }
            slicer.cli.run(
                slicer.modules.segmentations,
                None,
                effect_params,
                wait_for_completion=True,
            )

        return {"segmentation_out": seg_node}
