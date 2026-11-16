"""Nodes that put volumes on a common grid and combine them."""

import slicer
import sitkUtils
import SimpleITK as sitk

from .base_node import (SlicerBaseNode, VOLUME, TRANSFORM, _remove_mrml_node)


INTERPOLATORS = {
    'Linear':           sitk.sitkLinear,
    'Nearest Neighbor': sitk.sitkNearestNeighbor,
    'B-Spline':         sitk.sitkBSpline,
}


class ResampleVolumeNode(SlicerBaseNode):
    """
    Resamples a volume onto the grid of a reference volume, optionally moving it by a transform first.

    Use Nearest Neighbor for label volumes so label values are not blended.
    """

    NODE_NAME    = "Resample Volume"
    CATEGORY     = "Registration"

    INPUT_PORTS  = [
        ("volume_in",    "Volume",    VOLUME),
        ("reference_in", "Reference", VOLUME),
        ("transform_in", "Transform", TRANSFORM),
    ]
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'interpolation', 'label': 'Interpolation', 'type': 'enum',
         'default': 'Linear', 'items': list(INTERPOLATORS)},
        {'name': 'background', 'label': 'Background Value', 'type': 'float',
         'default': 0.0, 'min': -100000.0, 'max': 100000.0},
    ]

    def execute(self, inputs):
        volume = inputs.get('volume_in')
        reference = inputs.get('reference_in')
        transform = inputs.get('transform_in')
        if volume is None:
            raise ValueError("Resample Volume: no volume connected.")
        if reference is None:
            raise ValueError("Resample Volume: no reference connected.")
        interpolator = INTERPOLATORS.get(self.get_property('interpolation'))
        if interpolator is None:
            raise ValueError("Resample Volume: unknown interpolation "
                             f"'{self.get_property('interpolation')}'.")

        # Move a private copy by the transform, then read it back in its new position.
        # The input volume is left where it is.
        moved = volume
        temp = None
        if transform is not None:
            temp = slicer.mrmlScene.AddNewNodeByClass(
                volume.GetClassName(), '__NodeEditorResample__')
            temp.SetSaveWithScene(False)
            temp.CopyContent(volume)
            temp.SetAndObserveTransformNodeID(transform.GetID())
            slicer.vtkSlicerTransformLogic().hardenTransform(temp)
            moved = temp
        try:
            image = sitkUtils.PullVolumeFromSlicer(moved)
            grid = sitkUtils.PullVolumeFromSlicer(reference)
            result = sitk.Resample(
                image, grid, sitk.Transform(), interpolator,
                float(self.get_property('background')), image.GetPixelID())
        finally:
            if temp is not None:
                _remove_mrml_node(temp)

        out = self._get_or_create_output('volume_out',
                                         volume.GetName() + '_resampled')
        out.SetName(volume.GetName() + '_resampled')
        sitkUtils.PushVolumeToSlicer(result, out)
        return {'volume_out': out}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)


# ---------------------------------------------------------------------------
# Volume Math
# ---------------------------------------------------------------------------

def _as_float(a, b):
    return sitk.Cast(a, sitk.sitkFloat32), sitk.Cast(b, sitk.sitkFloat32)


MATH_OPERATIONS = {
    'A - B':        lambda a, b: sitk.Subtract(*_as_float(a, b)),
    'A + B':        lambda a, b: sitk.Add(*_as_float(a, b)),
    'A x B':        lambda a, b: sitk.Multiply(*_as_float(a, b)),
    '|A - B|':      lambda a, b: sitk.Abs(sitk.Subtract(*_as_float(a, b))),
    'Minimum':      lambda a, b: sitk.Minimum(*_as_float(a, b)),
    'Maximum':      lambda a, b: sitk.Maximum(*_as_float(a, b)),
    'Mean':         lambda a, b: sitk.Multiply(
                        sitk.Add(*_as_float(a, b)), 0.5),
}


class VolumeMathNode(SlicerBaseNode):
    """Combines two volumes voxel by voxel.
    Both must be on the same grid; put a Resample Volume node in front of one of them if they are not."""

    NODE_NAME    = "Volume Math"
    CATEGORY     = "Filters"

    INPUT_PORTS  = [("a_in", "A", VOLUME),
                    ("b_in", "B", VOLUME)]
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'operation', 'label': 'Operation', 'type': 'enum',
         'default': 'A - B', 'items': list(MATH_OPERATIONS)},
    ]

    def execute(self, inputs):
        a_node = inputs.get('a_in')
        b_node = inputs.get('b_in')
        if a_node is None or b_node is None:
            raise ValueError("Volume Math: both A and B must be connected.")
        operation = MATH_OPERATIONS.get(self.get_property('operation'))
        if operation is None:
            raise ValueError("Volume Math: unknown operation "
                             f"'{self.get_property('operation')}'.")
        a = sitkUtils.PullVolumeFromSlicer(a_node)
        b = sitkUtils.PullVolumeFromSlicer(b_node)
        if a.GetSize() != b.GetSize():
            raise ValueError(
                f"Volume Math: A is {a.GetSize()} voxels and B is "
                f"{b.GetSize()}. Resample one onto the other first.")
        # Same voxel counts: treat B as being on A's grid.
        # Small differences in origin or spacing metadata would otherwise make SimpleITK refuse the pair.
        b.CopyInformation(a)
        result = operation(a, b)

        out = self._get_or_create_output('volume_out',
                                         a_node.GetName() + '_math')
        out.SetName(a_node.GetName() + '_math')
        sitkUtils.PushVolumeToSlicer(result, out)
        return {'volume_out': out}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)
