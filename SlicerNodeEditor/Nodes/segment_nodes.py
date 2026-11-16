"""Segmentation nodes."""

import slicer
from .base_node import (SlicerBaseNode, LinkedModuleNode,
                         VOLUME, SEGMENTATION, _mark_ephemeral, _debug)


class SegmentationNode(SlicerBaseNode):
    NODE_NAME    = "Segmentation"
    CATEGORY     = "Segmentation"
    # Segmentation effects (especially via Segment Editor) are interactive and not safe to re-fire on every slider tick.
    AUTO_EXECUTE = False

    INPUT_PORTS  = [("volume_in", "Volume", VOLUME)]
    OUTPUT_PORTS = [("seg_out",   "Segmentation", SEGMENTATION)]

    PROPERTIES = [
        {'name': 'method', 'label': 'Method', 'type': 'enum',
         'default': 'Threshold',
         'items': ['Threshold', 'Otsu', 'Manual (Segment Editor)']},
        {'name': 'lower', 'label': 'Lower Threshold', 'type': 'float',
         'default': 100.0, 'min': -2000.0, 'max': 5000.0},
        {'name': 'upper', 'label': 'Upper Threshold', 'type': 'float',
         'default': 3000.0, 'min': -2000.0, 'max': 5000.0},
    ]

    def execute(self, inputs):
        volume_node = inputs.get('volume_in')
        if volume_node is None:
            raise ValueError("Segmentation: no input volume connected.")

        method = self.get_property('method')
        lower  = self.get_property('lower')
        upper  = self.get_property('upper')

        # Reuse the segmentation WE own (not whatever _cache currently holds; that may be an upstream ref left by passthrough).
        seg = self._owned_outputs.get('seg_out')
        if seg is None or not slicer.mrmlScene.GetNodeByID(seg.GetID()):
            seg = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode')
            seg.SetName(volume_node.GetName() + '_seg')
            seg.CreateDefaultDisplayNodes()
            seg.SetReferenceImageGeometryParameterFromVolumeNode(volume_node)
            _mark_ephemeral(seg)
            self._owned_outputs['seg_out'] = seg

        if seg.GetSegmentation().GetNumberOfSegments() == 0:
            seg.GetSegmentation().AddEmptySegment('Segment_1')

        if method in ('Threshold', 'Otsu'):
            # Write the mask straight into the segment.
            # Driving a Segment Editor widget for this leaves its threshold effect observing the slice views after the widget is dropped.
            seg.SetReferenceImageGeometryParameterFromVolumeNode(volume_node)
            voxels = slicer.util.arrayFromVolume(volume_node)
            if method == 'Otsu':
                import SimpleITK as sitk
                import sitkUtils
                otsu = sitk.OtsuThresholdImageFilter()
                otsu.Execute(sitkUtils.PullVolumeFromSlicer(volume_node))
                # Same convention as the Segment Editor's automatic threshold: from the Otsu value up to the maximum.
                mask = voxels >= otsu.GetThreshold()
            else:
                mask = (voxels >= lower) & (voxels <= upper)
            segment_id = seg.GetSegmentation().GetNthSegmentID(0)
            slicer.util.updateSegmentBinaryLabelmapFromArray(
                mask.astype('uint8'), seg, segment_id, volume_node)

        return {'seg_out': seg}

    def route_to_viewer(self):
        seg = self._cache.get('seg_out')
        if seg is None:
            return
        lm = slicer.app.layoutManager()
        lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView)
        # Show reference volume + segmentation overlay
        ref_vol = seg.GetNodeReference('referenceImageGeometryRef')
        if ref_vol:
            for color in ('Red', 'Yellow', 'Green'):
                cn = slicer.mrmlScene.GetNodeByID(
                    f'vtkMRMLSliceCompositeNode{color}')
                if cn:
                    cn.SetBackgroundVolumeID(ref_vol.GetID())
        seg.GetDisplayNode().SetVisibility(True)
        slicer.util.resetSliceViews()


# ---------------------------------------------------------------------------
# Segment Editor: linked to Slicer's "SegmentEditor" module
# ---------------------------------------------------------------------------

class SegmentEditorNode(LinkedModuleNode):
    # Paint-mode editing is the canonical operation here; auto-rerunning would clobber the user's in-progress strokes.
    AUTO_EXECUTE = False
    # Strokes cannot be recomputed from upstream.
    # When an upstream input changes, show the amber stale-input badge: the hand-edited segmentation may no longer align with its source volume.
    EDIT_STATE   = True
    """
    Interactive segmentation via Slicer's Segment Editor module.

    Connect a Volume input (and optionally an existing Segmentation to
    edit); double-click to open the Segment Editor with both pre-selected.
    The same segmentation flows out, so downstream nodes can consume it.
    """

    NODE_NAME     = "Segment Editor"
    CATEGORY      = "Segmentation"
    LINKED_MODULE = "SegmentEditor"

    INPUT_PORTS  = [
        ("volume_in", "Volume",       VOLUME),
        ("seg_in",    "Segmentation", SEGMENTATION),
    ]
    OUTPUT_PORTS = [("seg_out", "Segmentation", SEGMENTATION)]

    INPUT_SETTERS = {
        'volume_in': ('setSourceVolumeNode', 'setMasterVolumeNode'),
        'seg_in':    ('setSegmentationNode',),
    }

    def configure_module_widget(self, module_widget, node_item):
        """Point the Segment Editor at this node's segmentation and volume.
        The module is scripted: the editor widget that has the setters hangs off the module widget's Python object."""
        try:
            editor = module_widget.self().editor
        except Exception as exc:
            _debug(f"{self.NODE_NAME}: no editor widget: {exc}")
            return
        seg = self._cache.get('seg_out') or self._resolve_input(
            node_item, 'seg_in')
        vol = self._resolve_input(node_item, 'volume_in')
        if seg is not None:
            editor.setSegmentationNode(seg)
        if vol is not None:
            editor.setSourceVolumeNode(vol)

    def execute(self, inputs):
        # If no segmentation is fed in, create a fresh one bound to the volume so the user has something to edit immediately.
        seg = inputs.get('seg_in') or self._owned_outputs.get('seg_out')
        if seg is None or not slicer.mrmlScene.GetNodeByID(seg.GetID()):
            vol = inputs.get('volume_in')
            seg = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode')
            if vol is not None:
                seg.SetName(vol.GetName() + '_seg')
                seg.SetReferenceImageGeometryParameterFromVolumeNode(vol)
            seg.CreateDefaultDisplayNodes()
            _mark_ephemeral(seg)
            self._owned_outputs['seg_out'] = seg
        return {'seg_out': seg}

    def route_to_viewer(self):
        seg = self._cache.get('seg_out')
        vol = self._cache.get('volume_in')
        if seg is None:
            return
        if vol is not None:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(vol)
        try:
            seg.GetDisplayNode().SetVisibility(True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Segmentations: linked to Slicer's "Segmentations" module
# ---------------------------------------------------------------------------

class SegmentationsNode(LinkedModuleNode):
    """Edit segmentation properties via Slicer's Segmentations module."""

    NODE_NAME     = "Segmentations"
    CATEGORY      = "Segmentation"
    LINKED_MODULE = "Segmentations"

    INPUT_PORTS   = [("seg_in",  "Segmentation", SEGMENTATION)]
    OUTPUT_PORTS  = [("seg_out", "Segmentation", SEGMENTATION)]
    INPUT_SETTERS = {'seg_in': ('setSegmentationNode', 'setMRMLNode')}
