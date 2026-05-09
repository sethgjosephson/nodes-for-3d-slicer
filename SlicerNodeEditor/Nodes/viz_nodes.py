"""Visualization nodes."""

import slicer
from .base_node import SlicerBaseNode, VOLUME, SEGMENTATION


class VolumeRenderingNode(SlicerBaseNode):
    NODE_NAME     = "Volume Rendering"
    CATEGORY      = "Visualization"
    LINKED_MODULE = "VolumeRendering"

    INPUT_PORTS  = [("volume_in", "Volume", VOLUME)]
    OUTPUT_PORTS = []

    # No PROPERTIES — settings live in the native VR module widget,
    # which Slicer shows automatically when this node is selected.

    def execute(self, inputs):
        node = inputs.get('volume_in')
        if node is None:
            raise ValueError("Volume Rendering: no input volume connected.")
        # Cache the input so configure_module_widget / route_to_viewer can find it
        self._cache['volume_in'] = node

        vr_logic = slicer.modules.volumerendering.logic()

        # Get or create the volume rendering display node for this volume
        dn = vr_logic.GetFirstVolumeRenderingDisplayNode(node)
        if dn is None and hasattr(vr_logic, 'CreateDefaultVolumeRenderingNodes'):
            dn = vr_logic.CreateDefaultVolumeRenderingNodes(node)
        if dn is None:
            # Fallback for older Slicer versions
            dn = vr_logic.CreateVolumeRenderingDisplayNode()
            slicer.mrmlScene.AddNode(dn)
            node.AddAndObserveDisplayNodeID(dn.GetID())
            vr_logic.UpdateDisplayNodeFromVolumeNode(dn, node)

        return {}

    def route_to_viewer(self):
        """Show only THIS volume's rendering; hide all other VR displays."""
        vol = self._resolve_input_volume()
        target_id = None
        if vol is not None:
            vr_logic  = slicer.modules.volumerendering.logic()
            target_dn = vr_logic.GetFirstVolumeRenderingDisplayNode(vol)
            target_id = target_dn.GetID() if target_dn is not None else None

        # Flip visibility on every VR display node in the scene
        n = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLVolumeRenderingDisplayNode')
        for i in range(n):
            dn = slicer.mrmlScene.GetNthNodeByClass(i, 'vtkMRMLVolumeRenderingDisplayNode')
            if dn is not None:
                dn.SetVisibility(dn.GetID() == target_id)

        lm = slicer.app.layoutManager()
        lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)

    def configure_module_widget(self, module_widget, node_item):
        """Point the VR module widget at this node's input volume."""
        vol = self._resolve_input_volume(node_item=node_item)
        if vol is None:
            return
        for setter in ('setMRMLVolumeNode', 'setMRMLNode'):
            if hasattr(module_widget, setter):
                try:
                    getattr(module_widget, setter)(vol)
                    return
                except Exception:
                    continue

    def _resolve_input_volume(self, node_item=None):
        """
        Find the volume currently feeding our 'volume_in' port.
        Prefer walking the graph (always current); fall back to cache.
        """
        if node_item is not None:
            scene = node_item.scene()
            if scene is not None:
                in_port = node_item.get_port('volume_in', is_input=True)
                if in_port is not None and hasattr(scene, 'get_incoming_edge'):
                    edge = scene.get_incoming_edge(in_port)
                    if edge is not None and edge.source_port is not None:
                        up = edge.source_port.node_item.node_data
                        v  = up._cache.get(edge.source_port.port_name)
                        if v is not None:
                            return v
        return self._cache.get('volume_in')
