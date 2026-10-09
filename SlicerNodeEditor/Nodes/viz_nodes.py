"""Visualization nodes."""

import slicer
from .base_node import (SlicerBaseNode, LinkedModuleNode,
                         VOLUME, SEGMENTATION, MODEL, _mark_ephemeral,
                         _debug)


class VolumeRenderingNode(LinkedModuleNode):
    NODE_NAME     = "Volume Rendering"
    CATEGORY      = "Visualization"
    LINKED_MODULE = "VolumeRendering"

    INPUT_PORTS    = [("volume_in", "Volume", VOLUME)]
    OUTPUT_PORTS   = []
    INPUT_SETTERS  = {'volume_in': ('setMRMLVolumeNode', 'setMRMLNode')}

    # No PROPERTIES; settings live in the native VR module widget,
    # which Slicer shows automatically when this node is selected.

    # Attribute on the VR display node recording the volume property's
    # MTime as of our last automatic transfer-function sync. If the
    # property's MTime no longer matches, the user (or a preset) has
    # edited it: it is now hand-edited state and we never touch it again.
    VR_PROP_MTIME_ATTR = 'NodeEditor.AutoVRPropMTime'

    def execute(self, inputs):
        node = inputs.get('volume_in')
        if node is None:
            raise ValueError("Volume Rendering: no input volume connected.")
        # Cache the input so route_to_viewer / configure_module_widget can find it
        self._cache['volume_in'] = node

        vr_logic = slicer.modules.volumerendering.logic()

        dn = self._resolve_display_node(vr_logic, node)

        # The display node is created once, but the volume's DATA changes
        # on every upstream re-cook. Re-sync the transfer function from
        # the volume's current window/level so the rendering tracks the
        # data, unless the user has hand-tweaked the VR property.
        self._refresh_transfer_function(vr_logic, dn)

        return {}

    def _resolve_display_node(self, vr_logic, volume):
        """
        Return the ONE VR display node this graph node owns, creating it
        on first use and re-attaching it when the incoming volume's
        identity changes.

        Identity changes are routine here: disabling the filter that
        feeds this node (D-key passthrough) swaps in a different
        upstream MRML volume. Keying the display node by volume (the
        old behavior) made Slicer mint a fresh display node with a
        default fitted ROI on every such swap, so the user's cropping
        ROI and transfer function appeared to randomly reset. Owning
        one display node per GRAPH node keeps view state stable: the
        ROI and volume property travel with the display node across
        re-attachments.
        """
        dn = getattr(self, '_vr_display_node', None)
        if dn is not None:
            try:
                if not slicer.mrmlScene.GetNodeByID(dn.GetID()):
                    dn = None
            except Exception:
                dn = None

        if dn is None:
            # First use (or the display node died with a scene close):
            # adopt the volume's existing VR display node if it has one,
            # else create the default set (display + property + ROI).
            dn = vr_logic.GetFirstVolumeRenderingDisplayNode(volume)
            created = False
            if dn is None and hasattr(vr_logic, 'CreateDefaultVolumeRenderingNodes'):
                dn = vr_logic.CreateDefaultVolumeRenderingNodes(volume)
                created = dn is not None
            if dn is None:
                dn = vr_logic.CreateVolumeRenderingDisplayNode()
                slicer.mrmlScene.AddNode(dn)
                volume.AddAndObserveDisplayNodeID(dn.GetID())
                vr_logic.UpdateDisplayNodeFromVolumeNode(dn, volume)
                created = True
            if created and dn is not None:
                # The display node belongs to the graph, not the saved scene.
                _mark_ephemeral(dn)
            self._vr_display_node = dn
            return dn

        # Same volume still flowing in: nothing to do.
        owner = None
        try:
            owner = dn.GetDisplayableNode()
        except Exception:
            pass
        if (owner is not None and volume is not None
                and owner.GetID() == volume.GetID()):
            return dn

        # Volume identity changed (passthrough toggle, upstream rewire):
        # move OUR display node to the new volume. ROI and transfer
        # function ride along on the display node untouched.
        try:
            if owner is not None:
                for i in range(owner.GetNumberOfDisplayNodes()):
                    if owner.GetNthDisplayNodeID(i) == dn.GetID():
                        owner.RemoveNthDisplayNodeID(i)
                        break
            volume.AddAndObserveDisplayNodeID(dn.GetID())
        except Exception as exc:
            _debug(f"{self.NODE_NAME}: re-attaching display node failed: {exc}")
        return dn

    def _refresh_transfer_function(self, vr_logic, dn):
        """
        Keep the transfer function usable as the data changes, without
        stomping presets or hand-tweaks:

        - A property the user has edited (preset applied, curve dragged)
          is edit-state: never touched. Detected via the property
          MTime recorded in VR_PROP_MTIME_ATTR on our last visit.
        - Otherwise the preset stays in charge. Window/level sync (the
          VR module's "Synchronize with Volumes module") is ONLY a
          rescue for data the current function provably renders
          invisibly, e.g. a 0/1 mask under an anatomical preset whose
          opacity ramp lives at intensities in the hundreds. Syncing
          unconditionally replaces every preset with a flat grayscale
          ramp (black-and-white heads, solid gray CT blocks).
        """
        if dn is None:
            return
        try:
            prop = dn.GetVolumePropertyNode()
        except Exception:
            prop = None
        if prop is None:
            return

        recorded = None
        try:
            recorded = dn.GetAttribute(self.VR_PROP_MTIME_ATTR)
        except Exception:
            pass
        if recorded not in (None, '') and recorded != str(prop.GetMTime()):
            _debug(f"{self.NODE_NAME}: VR property was hand-edited "
                   f"(MTime {prop.GetMTime()} != recorded {recorded}); "
                   f"leaving transfer function untouched")
            return

        if self._renders_invisibly(prop, self._cache.get('volume_in')):
            try:
                vr_logic.CopyDisplayToVolumeRenderingDisplayNode(dn)
                _debug(f"{self.NODE_NAME}: transfer function had no "
                       f"opacity over the data's scalar range; re-synced "
                       f"from window/level as a rescue")
            except Exception as exc:
                _debug(f"{self.NODE_NAME}: transfer-function sync "
                       f"failed: {exc}")
                return

        # Stamp the state we're accepting (preset or synced) so a later
        # user edit is detectable as a hand-tweak.
        try:
            dn.SetAttribute(self.VR_PROP_MTIME_ATTR, str(prop.GetMTime()))
        except Exception:
            pass

    @staticmethod
    def _renders_invisibly(prop_node, volume):
        """
        True when the scalar opacity function is essentially zero across
        the volume's entire scalar range, i.e. the render would show
        nothing at all. Deliberately conservative: any nonzero opacity
        anywhere in the data range means "leave the preset alone".
        """
        try:
            vp = prop_node.GetVolumeProperty()
            so = vp.GetScalarOpacity() if vp is not None else None
            img = volume.GetImageData() if volume is not None else None
            if so is None or img is None:
                return False
            d0, d1 = img.GetScalarRange()
            if d1 <= d0:
                return False
            steps = 16
            max_opacity = 0.0
            for i in range(steps + 1):
                x = d0 + (d1 - d0) * i / steps
                max_opacity = max(max_opacity, so.GetValue(x))
            return max_opacity < 0.01
        except Exception:
            return False

    def _owned_display_node(self):
        """The display node this graph node owns, or None if it (or the
        scene) is gone. Routing must use THIS, not a lookup by volume:
        after a passthrough toggle the volume-keyed lookup could find a
        different node's display."""
        dn = getattr(self, '_vr_display_node', None)
        if dn is None:
            return None
        try:
            if not slicer.mrmlScene.GetNodeByID(dn.GetID()):
                return None
        except Exception:
            return None
        return dn

    def route_to_viewer(self):
        """Show this volume in 3D rendering AND keep slices populated.
        Uses the Conventional layout (3 slices + 3D pane) so the user
        sees both the rendering and the underlying anatomy.
        Other volumes' VR displays are hidden so only ours is visible
        in the 3D pane."""
        vol = self._cache.get('volume_in')
        target_dn = self._owned_display_node()
        target_id = target_dn.GetID() if target_dn is not None else None

        # Exclusive VR visibility
        n = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLVolumeRenderingDisplayNode')
        for i in range(n):
            dn = slicer.mrmlScene.GetNthNodeByClass(i, 'vtkMRMLVolumeRenderingDisplayNode')
            if dn is not None:
                dn.SetVisibility(dn.GetID() == target_id)

        # Route the input volume to the slice viewers (Conventional layout)
        if vol is not None:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(vol)
        else:
            slicer.app.layoutManager().setLayout(
                slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)

    def route_fullscreen(self):
        """F-key: pure 3D, no slice context."""
        target_dn = self._owned_display_node()
        if target_dn is not None:
            target_dn.SetVisibility(True)
        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)


# ---------------------------------------------------------------------------
# Models: passthrough wrapper around Slicer's Models module
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
        """Hide other models; show only this one. Use Conventional layout
        so slice context is preserved."""
        self._set_exclusive_visibility()
        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView)

    def route_fullscreen(self):
        """F-key: pure 3D, no slice context."""
        self._set_exclusive_visibility()
        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)

    def _set_exclusive_visibility(self):
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
