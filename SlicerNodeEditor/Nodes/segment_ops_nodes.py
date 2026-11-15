"""
Nodes that work on segmentations: clean-up filters, surface models,
statistics, masking a volume, and label map import.
"""

import slicer

from .base_node import (SlicerBaseNode, VOLUME, SEGMENTATION, MODEL, TABLE,
                         _mark_ephemeral, _remove_mrml_node)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _segment_ids(seg_node):
    seg = seg_node.GetSegmentation()
    return [seg.GetNthSegmentID(i) for i in range(seg.GetNumberOfSegments())]


class _ReferenceGeometry:
    """
    Context manager giving a volume node whose grid a segmentation's
    binary labelmaps can be read and written on.

    Uses the given volume if there is one. Otherwise exports the
    segmentation to a temporary labelmap on its reference geometry and
    removes that labelmap on exit.
    """

    def __init__(self, seg_node, volume=None):
        self._seg = seg_node
        self._volume = volume
        self._temp = None

    def __enter__(self):
        if self._volume is not None:
            return self._volume
        temp = slicer.mrmlScene.AddNewNodeByClass(
            'vtkMRMLLabelMapVolumeNode', '__NodeEditorGeometry__')
        temp.SetSaveWithScene(False)
        ok = slicer.modules.segmentations.logic().ExportAllSegmentsToLabelmapNode(
            self._seg, temp, slicer.vtkSegmentation.EXTENT_REFERENCE_GEOMETRY)
        if not ok or temp.GetImageData() is None:
            _remove_mrml_node(temp)
            raise ValueError("the segmentation is empty")
        self._temp = temp
        return temp

    def __exit__(self, *exc):
        if self._temp is not None:
            _remove_mrml_node(self._temp)
        return False


def _owned_node(node, port_name, mrml_class, name):
    """Return the MRML node `node` owns on `port_name`, creating it once."""
    existing = node._owned_outputs.get(port_name)
    if existing is not None and slicer.mrmlScene.GetNodeByID(existing.GetID()):
        existing.SetName(name)
        return existing, False
    new_node = slicer.mrmlScene.AddNewNodeByClass(mrml_class)
    new_node.SetName(name)
    if hasattr(new_node, 'CreateDefaultDisplayNodes'):   # tables have none
        new_node.CreateDefaultDisplayNodes()
    _mark_ephemeral(new_node)
    node._owned_outputs[port_name] = new_node
    return new_node, True


def _show_segmentation(seg, volume=None):
    lm = slicer.app.layoutManager()
    lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView)
    if volume is None:
        volume = seg.GetNodeReference(
            slicer.vtkMRMLSegmentationNode.GetReferenceImageGeometryReferenceRole())
    if volume is not None:
        from .io_nodes import _route_volume_to_slices
        _route_volume_to_slices(volume)
    for other in slicer.util.getNodesByClass('vtkMRMLSegmentationNode'):
        dn = other.GetDisplayNode()
        if dn is not None:
            dn.SetVisibility(other.GetID() == seg.GetID())


# ---------------------------------------------------------------------------
# Segment Filter
# ---------------------------------------------------------------------------

def _radius_vox(size_mm, spacing):
    """Kernel radius in voxels for a size in mm, at least one voxel.
    `spacing` is in SimpleITK order (x, y, z), as the kernel is."""
    return [max(1, int(round(float(size_mm) / s))) for s in spacing]


def _op_largest(sitk, img, p, spacing):
    cc = sitk.RelabelComponent(sitk.ConnectedComponent(img),
                               sortByObjectSize=True)
    return cc == 1


def _op_remove_small(sitk, img, p, spacing):
    cc = sitk.RelabelComponent(sitk.ConnectedComponent(img),
                               minimumObjectSize=int(p('min_voxels')))
    return cc > 0


def _op_median(sitk, img, p, spacing):
    return sitk.BinaryMedian(img, _radius_vox(p('size_mm'), spacing))


def _op_closing(sitk, img, p, spacing):
    return sitk.BinaryMorphologicalClosing(
        img, _radius_vox(p('size_mm'), spacing))


def _op_opening(sitk, img, p, spacing):
    return sitk.BinaryMorphologicalOpening(
        img, _radius_vox(p('size_mm'), spacing))


def _op_grow(sitk, img, p, spacing):
    return sitk.BinaryDilate(img, _radius_vox(p('size_mm'), spacing))


def _op_shrink(sitk, img, p, spacing):
    return sitk.BinaryErode(img, _radius_vox(p('size_mm'), spacing))


def _op_fill(sitk, img, p, spacing):
    return sitk.BinaryFillhole(img)


SEGMENT_OPERATIONS = {
    'Keep Largest Island': _op_largest,
    'Remove Small Islands': _op_remove_small,
    'Smooth (Median)': _op_median,
    'Smooth (Closing)': _op_closing,
    'Smooth (Opening)': _op_opening,
    'Grow': _op_grow,
    'Shrink': _op_shrink,
    'Fill Holes': _op_fill,
}


class SegmentFilterNode(SlicerBaseNode):
    """Applies one clean-up operation to every segment of a copy of the
    input segmentation."""

    NODE_NAME    = "Segment Filter"
    CATEGORY     = "Segmentation"

    INPUT_PORTS  = [("seg_in",    "Segmentation", SEGMENTATION),
                    ("volume_in", "Reference Volume", VOLUME)]
    OUTPUT_PORTS = [("seg_out",   "Segmentation", SEGMENTATION)]

    PROPERTIES = [
        {'name': 'operation', 'label': 'Operation', 'type': 'enum',
         'default': 'Keep Largest Island',
         'items': list(SEGMENT_OPERATIONS)},
        {'name': 'size_mm', 'label': 'Size (mm)', 'type': 'float',
         'default': 2.0, 'min': 0.1, 'max': 50.0},
        {'name': 'min_voxels', 'label': 'Minimum Island (vox)', 'type': 'int',
         'default': 1000, 'min': 1, 'max': 100000000},
    ]

    def execute(self, inputs):
        import numpy as np
        import SimpleITK as sitk

        seg_in = inputs.get('seg_in')
        if seg_in is None:
            raise ValueError("Segment Filter: no segmentation connected.")
        operation = SEGMENT_OPERATIONS.get(self.get_property('operation'))
        if operation is None:
            raise ValueError("Segment Filter: unknown operation "
                             f"'{self.get_property('operation')}'.")

        suffix = self.get_property('operation').lower().replace(' ', '_')
        out, _created = _owned_node(self, 'seg_out', 'vtkMRMLSegmentationNode',
                                    f"{seg_in.GetName()}_{suffix}")
        out.GetSegmentation().DeepCopy(seg_in.GetSegmentation())

        with _ReferenceGeometry(seg_in, inputs.get('volume_in')) as ref:
            out.SetReferenceImageGeometryParameterFromVolumeNode(ref)
            # Volume spacing is (x, y, z), the order SimpleITK kernels use.
            spacing = ref.GetSpacing()
            for sid in _segment_ids(out):
                arr = slicer.util.arrayFromSegmentBinaryLabelmap(out, sid, ref)
                img = sitk.GetImageFromArray((arr > 0).astype(np.uint8))
                result = operation(sitk, img, self.get_property, spacing)
                res = (sitk.GetArrayFromImage(result) > 0).astype(np.uint8)
                slicer.util.updateSegmentBinaryLabelmapFromArray(
                    res, out, sid, ref)
        volume = inputs.get('volume_in')
        if volume is not None:
            out.SetReferenceImageGeometryParameterFromVolumeNode(volume)
        self._cache['_volume'] = volume
        return {'seg_out': out}

    def route_to_viewer(self):
        seg = self._cache.get('seg_out')
        if seg is not None:
            _show_segmentation(seg, self._cache.get('_volume'))


# ---------------------------------------------------------------------------
# Surface Model
# ---------------------------------------------------------------------------

class SurfaceModelNode(SlicerBaseNode):
    """Builds one surface model from the segments of a segmentation."""

    NODE_NAME    = "Surface Model"
    CATEGORY     = "Segmentation"

    INPUT_PORTS  = [("seg_in",    "Segmentation", SEGMENTATION)]
    OUTPUT_PORTS = [("model_out", "Model", MODEL)]

    PROPERTIES = [
        {'name': 'segment', 'label': 'Segment Name (blank: all)',
         'type': 'str', 'default': ''},
        {'name': 'smoothing', 'label': 'Smoothing', 'type': 'float',
         'default': 0.5, 'min': 0.0, 'max': 1.0},
        {'name': 'decimation', 'label': 'Decimation', 'type': 'float',
         'default': 0.0, 'min': 0.0, 'max': 0.99},
    ]

    def execute(self, inputs):
        import vtk

        seg_in = inputs.get('seg_in')
        if seg_in is None:
            raise ValueError("Surface Model: no segmentation connected.")
        wanted = (self.get_property('segment') or '').strip()

        # Convert on a private copy: the surface settings are this node's,
        # and writing them into the input would change it for every other
        # consumer.
        temp = slicer.mrmlScene.AddNewNodeByClass(
            'vtkMRMLSegmentationNode', '__NodeEditorSurface__')
        temp.SetSaveWithScene(False)
        try:
            seg = temp.GetSegmentation()
            seg.DeepCopy(seg_in.GetSegmentation())
            surface = seg.GetClosedSurfaceRepresentationName() if hasattr(
                seg, 'GetClosedSurfaceRepresentationName') else (
                slicer.vtkSegmentationConverter
                .GetSegmentationClosedSurfaceRepresentationName())
            seg.RemoveRepresentation(surface)
            seg.SetConversionParameter(
                'Smoothing factor', str(float(self.get_property('smoothing'))))
            seg.SetConversionParameter(
                'Decimation factor',
                str(float(self.get_property('decimation'))))
            if not temp.CreateClosedSurfaceRepresentation():
                raise RuntimeError(
                    "Surface Model: could not build a surface.")

            append = vtk.vtkAppendPolyData()
            color = None
            used = 0
            for sid in _segment_ids(temp):
                segment = seg.GetSegment(sid)
                if wanted and segment.GetName() != wanted:
                    continue
                poly = vtk.vtkPolyData()
                temp.GetClosedSurfaceRepresentation(sid, poly)
                if poly.GetNumberOfPoints() == 0:
                    continue
                append.AddInputData(poly)
                used += 1
                if color is None:
                    color = segment.GetColor()
            if used == 0:
                if wanted:
                    raise ValueError(
                        f"Surface Model: no segment named '{wanted}' "
                        "with a surface.")
                raise ValueError("Surface Model: the segmentation is empty.")
            append.Update()
            mesh = vtk.vtkPolyData()
            mesh.DeepCopy(append.GetOutput())
        finally:
            _remove_mrml_node(temp)

        model, _created = _owned_node(self, 'model_out', 'vtkMRMLModelNode',
                                      seg_in.GetName() + '_surface')
        model.SetAndObservePolyData(mesh)
        model.SetAndObserveTransformNodeID(seg_in.GetTransformNodeID())
        dn = model.GetDisplayNode()
        if dn is not None and color is not None:
            dn.SetColor(*color)
        return {'model_out': model}

    def route_to_viewer(self):
        model = self._cache.get('model_out')
        if model is None:
            return
        for other in slicer.util.getNodesByClass('vtkMRMLModelNode'):
            if other.GetHideFromEditors():
                continue   # slice planes and other built-in models
            dn = other.GetDisplayNode()
            if dn is not None:
                dn.SetVisibility(other.GetID() == model.GetID())
        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView)
        slicer.util.resetThreeDViews()

    def route_fullscreen(self):
        self.route_to_viewer()
        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
        slicer.util.resetThreeDViews()


# ---------------------------------------------------------------------------
# Segment Statistics
# ---------------------------------------------------------------------------

def _show_table(table):
    slicer.app.layoutManager().setLayout(
        slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpTableView)
    logic = slicer.app.applicationLogic()
    logic.GetSelectionNode().SetActiveTableID(table.GetID())
    logic.PropagateTableSelection()


class SegmentStatisticsNode(SlicerBaseNode):
    """Computes per-segment statistics into a table."""

    NODE_NAME    = "Segment Statistics"
    CATEGORY     = "Measure"

    INPUT_PORTS  = [("seg_in",    "Segmentation", SEGMENTATION),
                    ("volume_in", "Volume", VOLUME)]
    OUTPUT_PORTS = [("table_out", "Table", TABLE)]

    def execute(self, inputs):
        import SegmentStatistics

        seg = inputs.get('seg_in')
        if seg is None:
            raise ValueError("Segment Statistics: no segmentation connected.")
        volume = inputs.get('volume_in')

        table, _created = _owned_node(self, 'table_out', 'vtkMRMLTableNode',
                                      seg.GetName() + '_statistics')
        logic = SegmentStatistics.SegmentStatisticsLogic()
        params = logic.getParameterNode()
        params.SetParameter("Segmentation", seg.GetID())
        if volume is not None:
            params.SetParameter("ScalarVolume", volume.GetID())
        else:
            params.UnsetParameter("ScalarVolume")
        logic.computeStatistics()
        logic.exportToTable(table)
        return {'table_out': table}

    def route_to_viewer(self):
        table = self._cache.get('table_out')
        if table is not None:
            _show_table(table)


# ---------------------------------------------------------------------------
# Mask Volume
# ---------------------------------------------------------------------------

class MaskVolumeNode(SlicerBaseNode):
    """Keeps the voxels of a volume that lie inside a segmentation."""

    NODE_NAME    = "Mask Volume"
    CATEGORY     = "Segmentation"

    INPUT_PORTS  = [("volume_in", "Volume", VOLUME),
                    ("seg_in",    "Segmentation", SEGMENTATION)]
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'fill', 'label': 'Fill Value', 'type': 'float',
         'default': 0.0, 'min': -100000.0, 'max': 100000.0},
        {'name': 'invert', 'label': 'Keep Outside', 'type': 'bool',
         'default': False},
    ]

    def execute(self, inputs):
        import numpy as np
        import SimpleITK as sitk
        import sitkUtils

        volume = inputs.get('volume_in')
        seg = inputs.get('seg_in')
        if volume is None:
            raise ValueError("Mask Volume: no volume connected.")
        if seg is None:
            raise ValueError("Mask Volume: no segmentation connected.")

        voxels = slicer.util.arrayFromVolume(volume)
        mask = np.zeros(voxels.shape, dtype=bool)
        for sid in _segment_ids(seg):
            mask |= slicer.util.arrayFromSegmentBinaryLabelmap(
                seg, sid, volume) > 0
        if self.get_property('invert'):
            mask = ~mask
        fill = np.array(self.get_property('fill')).astype(voxels.dtype)
        masked = np.where(mask, voxels, fill)

        source = sitkUtils.PullVolumeFromSlicer(volume)
        result = sitk.GetImageFromArray(masked)
        result.CopyInformation(source)
        out = self._get_or_create_output('volume_out',
                                         volume.GetName() + '_masked')
        out.SetName(volume.GetName() + '_masked')
        sitkUtils.PushVolumeToSlicer(result, out)
        return {'volume_out': out}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)


# ---------------------------------------------------------------------------
# Label Map to Segmentation
# ---------------------------------------------------------------------------

class LabelMapToSegmentationNode(SlicerBaseNode):
    """Turns a label volume into a segmentation, one segment per value."""

    NODE_NAME    = "Label Map to Segmentation"
    CATEGORY     = "Segmentation"

    MAX_LABELS   = 256

    INPUT_PORTS  = [("volume_in", "Label Volume", VOLUME)]
    OUTPUT_PORTS = [("seg_out",   "Segmentation", SEGMENTATION)]

    def execute(self, inputs):
        import numpy as np
        import vtk

        volume = inputs.get('volume_in')
        if volume is None:
            raise ValueError(
                "Label Map to Segmentation: no volume connected.")
        labels = np.rint(slicer.util.arrayFromVolume(volume)).astype(np.int32)
        count = len(np.unique(labels))
        if count > self.MAX_LABELS:
            raise ValueError(
                f"Label Map to Segmentation: the input has {count} distinct "
                "values. It does not look like a label map.")

        seg, _created = _owned_node(self, 'seg_out', 'vtkMRMLSegmentationNode',
                                    volume.GetName() + '_seg')
        temp = slicer.mrmlScene.AddNewNodeByClass(
            'vtkMRMLLabelMapVolumeNode', '__NodeEditorLabels__')
        temp.SetSaveWithScene(False)
        try:
            matrix = vtk.vtkMatrix4x4()
            volume.GetIJKToRASMatrix(matrix)
            temp.SetIJKToRASMatrix(matrix)
            slicer.util.updateVolumeFromArray(temp, labels)
            seg.GetSegmentation().RemoveAllSegments()
            seg.SetReferenceImageGeometryParameterFromVolumeNode(volume)
            ok = slicer.modules.segmentations.logic(
                ).ImportLabelmapToSegmentationNode(temp, seg)
            if not ok:
                raise RuntimeError(
                    "Label Map to Segmentation: import failed.")
        finally:
            _remove_mrml_node(temp)
        self._cache['_volume'] = volume
        return {'seg_out': seg}

    def route_to_viewer(self):
        seg = self._cache.get('seg_out')
        if seg is not None:
            _show_segmentation(seg, self._cache.get('_volume'))
