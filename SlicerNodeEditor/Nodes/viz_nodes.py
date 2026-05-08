"""Visualization nodes."""

import slicer
from .base_node import SlicerBaseNode, VOLUME, SEGMENTATION


class VolumeRenderingNode(SlicerBaseNode):
    NODE_NAME    = "Volume Rendering"
    CATEGORY     = "Visualization"

    INPUT_PORTS  = [("volume_in", "Volume", VOLUME)]
    OUTPUT_PORTS = []

    PROPERTIES = [
        {'name': 'preset', 'label': 'Preset', 'type': 'enum',
         'default': 'CT-Bones',
         'items': ['CT-Bones', 'CT-Chest', 'CT-AAA', 'CT-AAA2',
                   'CT-Cardiac', 'MR-Default', 'MR-Angio',
                   'MR-MIP', 'DTI']},
        {'name': 'visibility', 'label': 'Visible', 'type': 'bool',
         'default': True},
    ]

    def execute(self, inputs):
        node = inputs.get('volume_in')
        if node is None:
            raise ValueError("Volume Rendering: no input volume connected.")

        vr_logic = slicer.modules.volumerendering.logic()
        vr_logic.SetDefaultVolumeRenderingProperties(node)
        dn = vr_logic.GetFirstVolumeRenderingDisplayNode(node)
        if dn is None:
            dn = vr_logic.CreateDefaultVolumeRenderingDisplayNode(node)
            node.AddAndObserveDisplayNodeID(dn.GetID())

        preset_name = self.get_property('preset')
        preset_node = vr_logic.GetPresetByName(preset_name)
        if preset_node:
            dn.GetVolumePropertyNode().Copy(preset_node)

        dn.SetVisibility(self.get_property('visibility'))
        return {}

    def route_to_viewer(self):
        node = self._cache.get('volume_in') if 'volume_in' not in self._cache \
            else None
        # Switch to 3D-only view
        lm = slicer.app.layoutManager()
        lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
