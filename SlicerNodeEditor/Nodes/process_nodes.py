"""Volume processing nodes that wrap existing Slicer modules."""

import slicer
from .base_node import LinkedModuleNode, VOLUME, _mark_ephemeral


class CropVolumeNode(LinkedModuleNode):
    """
    Crop a volume using Slicer's Crop Volume module.

    Connect a volume; on activation an ROI is auto-created (if not already
    cached), the Crop Volume module's parameter node is wired up, and
    pressing 1 (or Execute) runs the crop and outputs the cropped volume.
    Double-click opens the Crop Volume module so the user can adjust the
    ROI / parameters directly.
    """

    NODE_NAME     = "Crop Volume"
    CATEGORY      = "Filters"
    LINKED_MODULE = "CropVolume"

    INPUT_PORTS   = [("volume_in",  "Volume", VOLUME)]
    OUTPUT_PORTS  = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'isotropic', 'label': 'Isotropic Resample', 'type': 'bool',
         'default': False},
        {'name': 'spacing',   'label': 'Spacing Scale', 'type': 'float',
         'default': 1.0, 'min': 0.1, 'max': 10.0},
    ]

    def execute(self, inputs):
        vol = inputs.get('volume_in')
        if vol is None:
            raise ValueError("Crop Volume: no input volume connected.")

        cv_logic = slicer.modules.cropvolume.logic()

        # Reuse or create the parameter node (ties together volume + ROI + output)
        param = self._cache.get('_param_node')
        if param is None or not slicer.mrmlScene.GetNodeByID(param.GetID()):
            param = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLCropVolumeParametersNode')
            param.SetName(vol.GetName() + '_cropParam')
            _mark_ephemeral(param)
        param.SetInputVolumeNodeID(vol.GetID())

        # Reuse or create the ROI markup
        roi = self._cache.get('_roi_node')
        if roi is None or not slicer.mrmlScene.GetNodeByID(roi.GetID()):
            roi = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsROINode')
            roi.SetName(vol.GetName() + '_roi')
            _mark_ephemeral(roi)
        param.SetROINodeID(roi.GetID())
        cv_logic.SnapROIToVoxelGrid(param)
        cv_logic.FitROIToInputVolume(param)

        # Reuse or create the output volume
        out = self._cache.get('volume_out')
        if out is None or not slicer.mrmlScene.GetNodeByID(out.GetID()):
            out = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
            out.SetName(vol.GetName() + '_cropped')
            out.CreateDefaultDisplayNodes()
            _mark_ephemeral(out)
        param.SetOutputVolumeNodeID(out.GetID())

        param.SetVoxelBased(not bool(self.get_property('isotropic')))
        param.SetIsotropicResampling(bool(self.get_property('isotropic')))
        param.SetSpacingScalingConst(float(self.get_property('spacing')))

        cv_logic.Apply(param)

        # Stash the helpers so subsequent runs reuse them
        self._cache['_param_node'] = param
        self._cache['_roi_node']   = roi
        return {'volume_out': out}

    def route_to_viewer(self):
        out = self._cache.get('volume_out')
        if out is not None:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(out)

    def configure_module_widget(self, module_widget, node_item):
        """Push our parameter node into the Crop Volume module widget."""
        param = self._cache.get('_param_node')
        if param is None:
            # Run a quick setup to create the param node if missing
            try:
                vol = self._resolve_input(node_item, 'volume_in')
                if vol is not None:
                    self.execute({'volume_in': vol})
                    param = self._cache.get('_param_node')
            except Exception:
                pass
        if param is None:
            return
        for setter in ('setParametersNode', 'setMRMLCropVolumeParametersNode'):
            if hasattr(module_widget, setter):
                try:
                    getattr(module_widget, setter)(param)
                    return
                except Exception:
                    continue
