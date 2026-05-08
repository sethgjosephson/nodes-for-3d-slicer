"""Registration nodes."""

import slicer
from .base_node import SlicerBaseNode, VOLUME, TRANSFORM


class RegistrationNode(SlicerBaseNode):
    NODE_NAME    = "Registration"
    CATEGORY     = "Registration"

    INPUT_PORTS  = [
        ("fixed_in",  "Fixed Volume",  VOLUME),
        ("moving_in", "Moving Volume", VOLUME),
    ]
    OUTPUT_PORTS = [
        ("registered_out", "Registered", VOLUME),
        ("transform_out",  "Transform",  TRANSFORM),
    ]

    PROPERTIES = [
        {'name': 'type', 'label': 'Registration Type', 'type': 'enum',
         'default': 'Rigid',
         'items': ['Rigid', 'Affine', 'BSpline']},
        {'name': 'sampling', 'label': 'Sampling %', 'type': 'float',
         'default': 0.2, 'min': 0.01, 'max': 1.0},
        {'name': 'init_mode', 'label': 'Initialisation', 'type': 'enum',
         'default': 'useGeometryAlign',
         'items': ['useGeometryAlign', 'useCenterOfHeadAlign',
                   'useMomentsAlign', 'Off']},
    ]

    def execute(self, inputs):
        fixed  = inputs.get('fixed_in')
        moving = inputs.get('moving_in')
        if fixed is None or moving is None:
            raise ValueError("Registration: both Fixed and Moving volumes must be connected.")

        reg_type  = self.get_property('type')
        sampling  = self.get_property('sampling')
        init_mode = self.get_property('init_mode')

        # Reuse or create output nodes
        xfm = self._cache.get('transform_out')
        if xfm is None or not slicer.mrmlScene.GetNodeByID(xfm.GetID()):
            xfm = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
            xfm.SetName(f"{moving.GetName()}_to_{fixed.GetName()}_xfm")

        reg_vol = self._cache.get('registered_out')
        if reg_vol is None or not slicer.mrmlScene.GetNodeByID(reg_vol.GetID()):
            reg_vol = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
            reg_vol.SetName(f"{moving.GetName()}_registered")
            reg_vol.CreateDefaultDisplayNodes()

        params = {
            'fixedVolume':           fixed,
            'movingVolume':          moving,
            'outputTransform':       xfm,
            'outputVolume':          reg_vol,
            'transformType':         reg_type,
            'initializeTransformMode': init_mode,
            'samplingPercentage':    sampling,
        }
        slicer.cli.runSync(slicer.modules.brainsfit, None, params)

        return {'registered_out': reg_vol, 'transform_out': xfm}

    def route_to_viewer(self):
        node = self._cache.get('registered_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)


class ApplyTransformNode(SlicerBaseNode):
    NODE_NAME    = "Apply Transform"
    CATEGORY     = "Registration"

    INPUT_PORTS  = [
        ("volume_in",    "Volume",    VOLUME),
        ("transform_in", "Transform", TRANSFORM),
    ]
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'harden', 'label': 'Harden Transform', 'type': 'bool',
         'default': False},
    ]

    def execute(self, inputs):
        vol = inputs.get('volume_in')
        xfm = inputs.get('transform_in')
        if vol is None:
            raise ValueError("Apply Transform: no volume connected.")
        if xfm is None:
            raise ValueError("Apply Transform: no transform connected.")

        vol.SetAndObserveTransformNodeID(xfm.GetID())

        if self.get_property('harden'):
            import slicer
            slicer.vtkSlicerTransformLogic().hardenTransform(vol)

        return {'volume_out': vol}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)
