"""Visualization nodes."""

import slicer
from .base_node import (SlicerBaseNode, LinkedModuleNode,
                         VOLUME, SEGMENTATION, MODEL, _mark_ephemeral)


class VolumeRenderingNode(LinkedModuleNode):
    NODE_NAME     = "Volume Rendering"
    CATEGORY      = "Visualization"
    LINKED_MODULE = "VolumeRendering"

    INPUT_PORTS    = [("volume_in", "Volume", VOLUME)]
    OUTPUT_PORTS   = []
    INPUT_SETTERS  = {'volume_in': ('setMRMLVolumeNode', 'setMRMLNode')}

    # No PROPERTIES — settings live in the native VR module widget,
    # which Slicer shows automatically when this node is selected.

    def execute(self, inputs):
        node = inputs.get('volume_in')
        if node is None:
            raise ValueError("Volume Rendering: no input volume connected.")
        # Cache the input so route_to_viewer / configure_module_widget can find it
        self._cache['volume_in'] = node

        vr_logic = slicer.modules.volumerendering.logic()

        dn = vr_logic.GetFirstVolumeRenderingDisplayNode(node)
        dn_was_just_created = False
        if dn is None and hasattr(vr_logic, 'CreateDefaultVolumeRenderingNodes'):
            dn = vr_logic.CreateDefaultVolumeRenderingNodes(node)
            dn_was_just_created = dn is not None
        if dn is None:
            dn = vr_logic.CreateVolumeRenderingDisplayNode()
            slicer.mrmlScene.AddNode(dn)
            node.AddAndObserveDisplayNodeID(dn.GetID())
            vr_logic.UpdateDisplayNodeFromVolumeNode(dn, node)
            dn_was_just_created = True

        # The display node belongs to the graph, not the user's saved scene.
        if dn_was_just_created and dn is not None:
            _mark_ephemeral(dn)

        return {}

    def route_to_viewer(self):
        """Show only THIS volume's rendering; hide all other VR displays."""
        vol = self._cache.get('volume_in')
        target_id = None
        if vol is not None:
            vr_logic  = slicer.modules.volumerendering.logic()
            target_dn = vr_logic.GetFirstVolumeRenderingDisplayNode(vol)
            target_id = target_dn.GetID() if target_dn is not None else None

        n = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLVolumeRenderingDisplayNode')
        for i in range(n):
            dn = slicer.mrmlScene.GetNthNodeByClass(i, 'vtkMRMLVolumeRenderingDisplayNode')
            if dn is not None:
                dn.SetVisibility(dn.GetID() == target_id)

        lm = slicer.app.layoutManager()
        lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)


# ---------------------------------------------------------------------------
# Models — passthrough wrapper around Slicer's Models module
# ---------------------------------------------------------------------------

class ModelsNode(LinkedModuleNode):
    """View / edit model display properties via Slicer's Models module."""

    NODE_NAME     = "Models"
    CATEGORY      = "Visualization"
    LINKED_MODULE = "Models"

    INPUT_PORTS   = [("model_in",  "Model", MODEL)]
    OUTPUT_PORTS  = [("model_out", "Model", MODEL)]
    INPUT_SETTERS = {'model_in': ('setMRMLModelNode', 'setMRMLNode')}

    def route_to_viewer(self):
        """Hide other models; show only this one in the 3D view."""
        target = self._cache.get('model_in')
        target_id = target.GetID() if target is not None else None
        n = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLModelNode')
        for i in range(n):
            m = slicer.mrmlScene.GetNthNodeByClass(i, 'vtkMRMLModelNode')
            if m is None:
                continue
            dn = m.GetDisplayNode()
            if dn is None:
                continue
            try:
                dn.SetVisibility(m.GetID() == target_id)
            except Exception:
                pass
        lm = slicer.app.layoutManager()
        lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
