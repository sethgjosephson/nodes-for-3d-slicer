"""Segmentation nodes."""

import slicer
from .base_node import SlicerBaseNode, VOLUME, SEGMENTATION


class SegmentationNode(SlicerBaseNode):
    NODE_NAME    = "Segmentation"
    CATEGORY     = "Segmentation"

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
