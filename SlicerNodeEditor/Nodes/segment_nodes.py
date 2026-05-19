"""Segmentation nodes."""

import slicer
from .base_node import (SlicerBaseNode, LinkedModuleNode,
                         VOLUME, SEGMENTATION, _mark_ephemeral)


class SegmentationNode(SlicerBaseNode):
    NODE_NAME    = "Segmentation"
    CATEGORY     = "Segmentation"
    # Segmentation effects (especially via Segment Editor) are interactive
    # and not safe to re-fire on every slider tick.
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

        # Reuse or create segmentation node
        seg = self._cache.get('seg_out')
        if seg is None or not slicer.mrmlScene.GetNodeByID(seg.GetID()):
            seg = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode')
            seg.SetName(volume_node.GetName() + '_seg')
            seg.CreateDefaultDisplayNodes()
            seg.SetReferenceImageGeometryParameterFromVolumeNode(volume_node)
            _mark_ephemeral(seg)

        if seg.GetSegmentation().GetNumberOfSegments() == 0:
            seg.GetSegmentation().AddEmptySegment('Segment_1')

        if method in ('Threshold', 'Otsu'):
            # Use Segment Editor's threshold effect programmatically
            seg_editor_node = slicer.mrmlScene.AddNewNodeByClass(
                'vtkMRMLSegmentEditorNode')
            seg_editor_node.SetName('__NodeEditorTemp__')

            seg_widget = slicer.qMRMLSegmentEditorWidget()
            seg_widget.setMRMLScene(slicer.mrmlScene)
            seg_widget.setMRMLSegmentEditorNode(seg_editor_node)
            seg_widget.setSegmentationNode(seg)
            seg_widget.setSourceVolumeNode(volume_node)

            if method == 'Threshold':
                seg_widget.setActiveEffectByName('Threshold')
                effect = seg_widget.activeEffect()
                effect.setParameter('MinimumThreshold', str(lower))
                effect.setParameter('MaximumThreshold', str(upper))
                effect.self().onApply()
            elif method == 'Otsu':
                seg_widget.setActiveEffectByName('Threshold')
                effect = seg_widget.activeEffect()
                effect.self().onAutoThreshold(
                    'OTSU', 'SET_LOWER_MAX')
                effect.self().onApply()

            slicer.mrmlScene.RemoveNode(seg_editor_node)

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
# Segment Editor — linked to Slicer's "SegmentEditor" module
# ---------------------------------------------------------------------------

class SegmentEditorNode(LinkedModuleNode):
    # Paint-mode editing is the canonical operation here; auto-rerunning
    # would clobber the user's in-progress strokes.
    AUTO_EXECUTE = False
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

    def execute(self, inputs):
        # If no segmentation is fed in, create a fresh one bound to the
        # volume so the user has something to edit immediately.
        seg = inputs.get('seg_in') or self._cache.get('seg_out')
        if seg is None or not slicer.mrmlScene.GetNodeByID(seg.GetID()):
            vol = inputs.get('volume_in')
            seg = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode')
            if vol is not None:
                seg.SetName(vol.GetName() + '_seg')
                seg.SetReferenceImageGeometryParameterFromVolumeNode(vol)
            seg.CreateDefaultDisplayNodes()
            _mark_ephemeral(seg)
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
# Segmentations — linked to Slicer's "Segmentations" module
# ---------------------------------------------------------------------------

class SegmentationsNode(LinkedModuleNode):
    """Edit segmentation properties via Slicer's Segmentations module."""

    NODE_NAME     = "Segmentations"
    CATEGORY      = "Segmentation"
    LINKED_MODULE = "Segmentations"

    INPUT_PORTS   = [("seg_in",  "Segmentation", SEGMENTATION)]
    OUTPUT_PORTS  = [("seg_out", "Segmentation", SEGMENTATION)]
    INPUT_SETTERS = {'seg_in': ('setSegmentationNode', 'setMRMLNode')}
