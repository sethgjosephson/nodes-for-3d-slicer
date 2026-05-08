"""Visualization nodes."""

import slicer
from NodeGraph.node import SlicerBaseNode


class VolumeRenderingNode(SlicerBaseNode):
    __identifier__ = "slicer.viz"
    NODE_NAME = "Volume Rendering"
    NODE_COLOR = (60, 120, 150)

    INPUT_PORTS = [("volume_in", "Volume")]
    OUTPUT_PORTS = []

    def __init__(self):
        super().__init__()
        self.add_combo_menu("preset", "Preset", items=["CT-Bones", "CT-Chest", "MR-Default", "CT-AAA"])

    def execute(self, inputs: dict) -> dict:
        node = inputs.get("volume_in")
        if node is None:
            raise ValueError("Volume Rendering: no input volume connected.")

        vr_logic = slicer.modules.volumerendering.logic()
        vr_logic.SetDefaultVolumeRenderingProperties(node)
        display_node = vr_logic.GetFirstVolumeRenderingDisplayNode(node)
        if display_node is None:
            display_node = vr_logic.CreateDefaultVolumeRenderingDisplayNode(node)
            node.AddAndObserveDisplayNodeID(display_node.GetID())

        preset_name = self.get_property("preset")
        preset_node = vr_logic.GetPresetByName(preset_name)
        if preset_node:
            display_node.GetVolumePropertyNode().Copy(preset_node)

        display_node.SetVisibility(True)
        return {}
