"""Image filter nodes: threshold, smooth, and more."""

import slicer
import sitkUtils
import SimpleITK as sitk

from .base_node import SlicerBaseNode, VOLUME


class ThresholdNode(SlicerBaseNode):
    NODE_NAME    = "Threshold"
    CATEGORY     = "Filters"

    INPUT_PORTS  = [("volume_in",  "Volume", VOLUME)]
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'lower', 'label': 'Lower',  'type': 'float',
         'default': 100.0, 'min': -2000.0, 'max': 5000.0},
        {'name': 'upper', 'label': 'Upper',  'type': 'float',
         'default': 500.0, 'min': -2000.0, 'max': 5000.0},
        {'name': 'outside', 'label': 'Outside Value', 'type': 'float',
         'default': 0.0, 'min': -2000.0, 'max': 5000.0},
    ]

    def execute(self, inputs):
        node = inputs.get('volume_in')
        if node is None:
            raise ValueError("Threshold: no input volume connected.")

        lower   = self.get_property('lower')
        upper   = self.get_property('upper')
        outside = self.get_property('outside')

        img    = sitkUtils.PullVolumeFromSlicer(node)
        result = sitk.BinaryThreshold(
            img, lowerThreshold=lower, upperThreshold=upper,
            insideValue=1, outsideValue=outside)

        out = self._get_or_create_output('volume_out',
                                         node.GetName() + '_thresh')
        sitkUtils.PushVolumeToSlicer(result, out)
        return {'volume_out': out}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)


class GaussianSmoothNode(SlicerBaseNode):
    NODE_NAME    = "Gaussian Smooth"
    CATEGORY     = "Filters"

    INPUT_PORTS  = [("volume_in",  "Volume", VOLUME)]
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'sigma', 'label': 'Sigma (mm)', 'type': 'float',
         'default': 1.0, 'min': 0.1, 'max': 20.0},
    ]

    def execute(self, inputs):
        node = inputs.get('volume_in')
        if node is None:
            raise ValueError("Gaussian Smooth: no input volume connected.")

        sigma  = self.get_property('sigma')
        img    = sitkUtils.PullVolumeFromSlicer(node)
        result = sitk.SmoothingRecursiveGaussian(img, sigma=sigma)

        out = self._get_or_create_output('volume_out',
                                         node.GetName() + '_smooth')
        sitkUtils.PushVolumeToSlicer(result, out)
        return {'volume_out': out}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)


class MedianFilterNode(SlicerBaseNode):
    NODE_NAME    = "Median Filter"
    CATEGORY     = "Filters"

    INPUT_PORTS  = [("volume_in",  "Volume", VOLUME)]
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'radius', 'label': 'Radius (vox)', 'type': 'int',
         'default': 1, 'min': 1, 'max': 10},
    ]

    def execute(self, inputs):
        node = inputs.get('volume_in')
        if node is None:
            raise ValueError("Median Filter: no input volume connected.")
        r      = self.get_property('radius')
        img    = sitkUtils.PullVolumeFromSlicer(node)
        result = sitk.Median(img, [r, r, r])
        out = self._get_or_create_output('volume_out',
                                         node.GetName() + '_median')
        sitkUtils.PushVolumeToSlicer(result, out)
        return {'volume_out': out}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)


