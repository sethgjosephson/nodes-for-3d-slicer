"""Volume processing nodes that wrap existing Slicer modules."""

import slicer
from .base_node import LinkedModuleNode, VOLUME, MARKUP, _mark_ephemeral


class CropVolumeNode(LinkedModuleNode):
    """
    Crop a volume using Slicer's Crop Volume module.

    Connect a volume; on activation an ROI is auto-created (if not already
    cached), the Crop Volume module's parameter node is wired up, and
    pressing 1 (or Execute) runs the crop and outputs the cropped volume.
    Double-click opens the Crop Volume module so the user can adjust the
    ROI / parameters directly.

    The ROI is fitted to the input once, when it is created. After that
    it belongs to the user: dragging it in the views re-runs the crop,
    and its center and size are kept in the node's properties
    ('roi_center', 'roi_size') so they are saved with the graph.
    """

    NODE_NAME     = "Crop Volume"
    CATEGORY      = "Filters"
    LINKED_MODULE = "CropVolume"

    INPUT_PORTS   = [("volume_in",  "Volume", VOLUME),
                     ("roi_in",     "ROI",    MARKUP)]
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

        # An ROI connected to the input port is used as it is. It belongs
        # to the upstream node, which keeps and saves its placement.
        external_roi = inputs.get('roi_in')
        if external_roi is not None:
            if not external_roi.IsA('vtkMRMLMarkupsROINode'):
                raise ValueError(
                    "Crop Volume: the ROI input must be an ROI markup.")
            if external_roi.GetNumberOfControlPoints() == 0:
                raise ValueError(
                    "Crop Volume: the connected ROI has not been placed.")
            param.SetROINodeID(external_roi.GetID())
            return self._apply_crop(cv_logic, param, vol)

        # Reuse or create the ROI markup
        roi = self._cache.get('_roi_node')
        if roi is None or not slicer.mrmlScene.GetNodeByID(roi.GetID()):
            roi = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsROINode')
            roi.SetName(vol.GetName() + '_roi')
            _mark_ephemeral(roi)
            param.SetROINodeID(roi.GetID())
            center = self.get_property('roi_center')
            size = self.get_property('roi_size')
            if center and size:
                # A saved graph (or an undo) carries the ROI the user set.
                roi.SetCenter(*center)
                roi.SetSize(*size)
            else:
                cv_logic.SnapROIToVoxelGrid(param)
                cv_logic.FitROIToInputVolume(param)
        else:
            center = self.get_property('roi_center')
            size = self.get_property('roi_size')
            if (center and size
                    and (list(roi.GetCenter()) != list(center)
                         or list(roi.GetSize()) != list(size))):
                # Properties changed under us (undo, redo): follow them.
                roi.SetCenter(*center)
                roi.SetSize(*size)
        param.SetROINodeID(roi.GetID())
        result = self._apply_crop(cv_logic, param, vol)
        self._cache['_roi_node'] = roi
        self._store_roi(roi)
        self._watch_setting_node('roi', roi)
        return result

    def _apply_crop(self, cv_logic, param, vol):
        """Run the crop with the ROI already set on `param`."""
        # Reuse the cropped-volume node WE own. (_cache may carry an
        # upstream ref left by passthrough; that is not safe to write
        # CropVolume output into.)
        out = self._owned_outputs.get('volume_out')
        if out is None or not slicer.mrmlScene.GetNodeByID(out.GetID()):
            out = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
            out.SetName(vol.GetName() + '_cropped')
            out.CreateDefaultDisplayNodes()
            _mark_ephemeral(out)
            self._owned_outputs['volume_out'] = out
        param.SetOutputVolumeNodeID(out.GetID())

        param.SetVoxelBased(not bool(self.get_property('isotropic')))
        param.SetIsotropicResampling(bool(self.get_property('isotropic')))
        param.SetSpacingScalingConst(float(self.get_property('spacing')))

        cv_logic.Apply(param)

        # Stash the helper so subsequent runs reuse it
        self._cache['_param_node'] = param
        return {'volume_out': out}

    def _store_roi(self, roi):
        self._props['roi_center'] = [float(v) for v in roi.GetCenter()]
        self._props['roi_size']   = [float(v) for v in roi.GetSize()]

    def _on_setting_changed(self, key, mrml_node):
        if key == 'roi':
            self._store_roi(mrml_node)

    def release_outputs(self):
        for key in ('_param_node', '_roi_node'):
            helper = self._cache.get(key)
            try:
                if (helper is not None and slicer.mrmlScene.GetNodeByID(
                        helper.GetID()) is not None):
                    slicer.mrmlScene.RemoveNode(helper)
            except Exception:
                pass
        LinkedModuleNode.release_outputs(self)

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
