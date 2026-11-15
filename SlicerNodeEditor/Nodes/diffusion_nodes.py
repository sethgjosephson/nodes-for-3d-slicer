"""
Diffusion MRI nodes: diffusion-weighted volume in, tensor, scalar maps,
tractography and fiber measurements out.

Every node here runs a module of the SlicerDMRI extension. Without the
extension the nodes still load, so a saved graph keeps its shape; they
raise a clear error when run.
"""

import os

import slicer

from .base_node import (SlicerBaseNode, LinkedModuleNode, VOLUME, TABLE,
                         DWI, TENSOR, FIBERS,
                         _mark_ephemeral, _remove_mrml_node, _debug)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _dmri_module(name):
    module = getattr(slicer.modules, name, None)
    if module is None:
        raise RuntimeError(
            "This node needs the SlicerDMRI extension. Install it from "
            "the Extensions Manager and restart Slicer.")
    return module


def _run_cli(module, params, what):
    """Run a CLI module and wait for it. Raises with the module's own
    error text if it does not complete."""
    # Slicer shows a module's output volumes in the slice views when the
    # module finishes. What the views show is the viewed node's decision,
    # so put the slice layers back as they were.
    layers = _slice_layers()
    cli = slicer.cli.runSync(module, None, params)
    _restore_slice_layers(layers)
    try:
        if cli.GetStatus() != cli.Completed:
            detail = (cli.GetErrorText() or '').strip().splitlines()
            raise RuntimeError(
                f"{what} failed: {cli.GetStatusString()}"
                + (f" ({detail[-1]})" if detail else ""))
    finally:
        _remove_mrml_node(cli)


def _slice_layers():
    layers = []
    for composite in slicer.util.getNodesByClass('vtkMRMLSliceCompositeNode'):
        layers.append((composite, composite.GetBackgroundVolumeID(),
                       composite.GetForegroundVolumeID(),
                       composite.GetLabelVolumeID()))
    return layers


def _restore_slice_layers(layers):
    for composite, background, foreground, label in layers:
        composite.SetBackgroundVolumeID(background)
        composite.SetForegroundVolumeID(foreground)
        composite.SetLabelVolumeID(label)
    selection = slicer.app.applicationLogic().GetSelectionNode()
    if selection is not None and layers:
        selection.SetActiveVolumeID(layers[0][1])
        selection.SetActiveLabelVolumeID(layers[0][3])


def _owned(node, port_name, mrml_class, name):
    """The MRML node `node` owns on `port_name`, created on first use."""
    existing = node._owned_outputs.get(port_name)
    if existing is not None and slicer.mrmlScene.GetNodeByID(existing.GetID()):
        existing.SetName(name)
        return existing
    new_node = slicer.mrmlScene.AddNewNodeByClass(mrml_class)
    new_node.SetName(name)
    _mark_ephemeral(new_node)
    node._owned_outputs[port_name] = new_node
    return new_node


def _finish_outputs(*mrml_nodes):
    """CLI modules add display and storage nodes to their outputs when
    they load the result. Mark those as graph data too."""
    for mrml_node in mrml_nodes:
        if mrml_node is not None:
            _mark_ephemeral(mrml_node)


def _show_volume(volume):
    from .io_nodes import _route_volume_to_slices
    _route_volume_to_slices(volume)


# ---------------------------------------------------------------------------
# Sample DWI
# ---------------------------------------------------------------------------

class SampleDWINode(SlicerBaseNode):
    """Loads Slicer's sample diffusion-weighted volume."""

    NODE_NAME    = "Sample DWI"
    CATEGORY     = "Diffusion"

    INPUT_PORTS  = []
    OUTPUT_PORTS = [("dwi_out", "DWI", DWI)]

    def execute(self, inputs):
        import SampleData
        from .io_nodes import _cleanup_loaded_nodes, _snapshot_scene_node_ids
        _cleanup_loaded_nodes(self)
        self._cache.pop('dwi_out', None)

        before = set(_snapshot_scene_node_ids())
        dwi = SampleData.SampleDataLogic().downloadSample('DWIVolume')
        if dwi is None:
            raise RuntimeError("Sample DWI: the sample could not be loaded.")
        self._loaded_node_ids = [nid for nid in _snapshot_scene_node_ids()
                                 if nid not in before]
        for nid in self._loaded_node_ids:
            _mark_ephemeral(slicer.mrmlScene.GetNodeByID(nid))
        return {'dwi_out': dwi}

    def release_outputs(self):
        from .io_nodes import _cleanup_loaded_nodes
        _cleanup_loaded_nodes(self)
        SlicerBaseNode.release_outputs(self)

    def route_to_viewer(self):
        dwi = self._cache.get('dwi_out')
        if dwi is not None:
            _show_volume(dwi)


# ---------------------------------------------------------------------------
# DWI Mask
# ---------------------------------------------------------------------------

class DWIMaskNode(SlicerBaseNode):
    """Makes a brain mask and a baseline image from a DWI."""

    NODE_NAME    = "DWI Mask"
    CATEGORY     = "Diffusion"

    INPUT_PORTS  = [("dwi_in", "DWI", DWI)]
    OUTPUT_PORTS = [("mask_out",     "Mask",     VOLUME),
                    ("baseline_out", "Baseline", VOLUME)]

    PROPERTIES = [
        {'name': 'remove_islands', 'label': 'Remove Islands', 'type': 'bool',
         'default': True},
    ]

    def execute(self, inputs):
        dwi = inputs.get('dwi_in')
        if dwi is None:
            raise ValueError("DWI Mask: no DWI connected.")
        module = _dmri_module('diffusionweightedvolumemasking')
        mask = _owned(self, 'mask_out', 'vtkMRMLLabelMapVolumeNode',
                      dwi.GetName() + '_mask')
        baseline = _owned(self, 'baseline_out', 'vtkMRMLScalarVolumeNode',
                          dwi.GetName() + '_baseline')
        _run_cli(module, {
            'inputVolume': dwi,
            'outputBaseline': baseline,
            'thresholdMask': mask,
            'removeIslands': bool(self.get_property('remove_islands')),
        }, "DWI Mask")
        _finish_outputs(mask, baseline)
        return {'mask_out': mask, 'baseline_out': baseline}

    def route_to_viewer(self):
        baseline = self._cache.get('baseline_out')
        mask = self._cache.get('mask_out')
        if baseline is None:
            return
        _show_volume(baseline)
        if mask is not None:
            for color in ('Red', 'Yellow', 'Green'):
                cn = slicer.mrmlScene.GetNodeByID(
                    f'vtkMRMLSliceCompositeNode{color}')
                if cn is not None:
                    cn.SetLabelVolumeID(mask.GetID())


# ---------------------------------------------------------------------------
# Tensor Estimation
# ---------------------------------------------------------------------------

class TensorEstimationNode(SlicerBaseNode):
    """Fits a diffusion tensor to a DWI."""

    NODE_NAME    = "Tensor Estimation"
    CATEGORY     = "Diffusion"

    INPUT_PORTS  = [("dwi_in",  "DWI",  DWI),
                    ("mask_in", "Mask", VOLUME)]
    OUTPUT_PORTS = [("tensor_out",   "Tensor",   TENSOR),
                    ("baseline_out", "Baseline", VOLUME)]

    PROPERTIES = [
        {'name': 'method', 'label': 'Method', 'type': 'enum',
         'default': 'LS', 'items': ['LS', 'WLS']},
        {'name': 'shift_negative', 'label': 'Shift Negative Eigenvalues',
         'type': 'bool', 'default': False},
    ]

    def execute(self, inputs):
        dwi = inputs.get('dwi_in')
        if dwi is None:
            raise ValueError("Tensor Estimation: no DWI connected.")
        module = _dmri_module('dwitodtiestimation')
        tensor = _owned(self, 'tensor_out',
                        'vtkMRMLDiffusionTensorVolumeNode',
                        dwi.GetName() + '_tensor')
        baseline = _owned(self, 'baseline_out', 'vtkMRMLScalarVolumeNode',
                          dwi.GetName() + '_baseline')
        params = {
            'inputVolume': dwi,
            'outputTensor': tensor,
            'outputBaseline': baseline,
            'estimationMethod': self.get_property('method'),
            'ShiftNegativeEigenvalues': bool(
                self.get_property('shift_negative')),
        }
        with _LabelMap(inputs.get('mask_in')) as mask:
            if mask is not None:
                params['inputMaskVolume'] = mask
            _run_cli(module, params, "Tensor Estimation")
        _finish_outputs(tensor, baseline)
        return {'tensor_out': tensor, 'baseline_out': baseline}

    def route_to_viewer(self):
        tensor = self._cache.get('tensor_out')
        if tensor is not None:
            _show_volume(tensor)


class _LabelMap:
    """
    Context manager handing a CLI module a label map.

    The diffusion modules take masks and seed regions as label map nodes.
    A mask from a filter node is a plain scalar volume, so it is copied
    into a temporary label map for the run.
    """

    def __init__(self, volume):
        self._volume = volume
        self._temp = None

    def __enter__(self):
        v = self._volume
        if v is None or v.IsA('vtkMRMLLabelMapVolumeNode'):
            return v
        import numpy as np
        import vtk
        temp = slicer.mrmlScene.AddNewNodeByClass(
            'vtkMRMLLabelMapVolumeNode', '__NodeEditorLabel__')
        temp.SetSaveWithScene(False)
        matrix = vtk.vtkMatrix4x4()
        v.GetIJKToRASMatrix(matrix)
        temp.SetIJKToRASMatrix(matrix)
        slicer.util.updateVolumeFromArray(
            temp, np.rint(slicer.util.arrayFromVolume(v)).astype(np.int16))
        self._temp = temp
        return temp

    def __exit__(self, *exc):
        if self._temp is not None:
            _remove_mrml_node(self._temp)
        return False


# ---------------------------------------------------------------------------
# Tensor Scalars
# ---------------------------------------------------------------------------

TENSOR_SCALARS = [
    'FractionalAnisotropy', 'Trace', 'MeanDiffusivity', 'RelativeAnisotropy',
    'LinearMeasure', 'PlanarMeasure', 'SphericalMeasure',
    'MinEigenvalue', 'MidEigenvalue', 'MaxEigenvalue',
    'ParallelDiffusivity', 'PerpendicularDiffusivity', 'Mode',
    'Determinant',
]


class TensorScalarsNode(SlicerBaseNode):
    """Computes one scalar map (FA, MD and others) from a tensor volume."""

    NODE_NAME    = "Tensor Scalars"
    CATEGORY     = "Diffusion"

    INPUT_PORTS  = [("tensor_in",  "Tensor", TENSOR)]
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'operation', 'label': 'Measure', 'type': 'enum',
         'default': 'FractionalAnisotropy', 'items': TENSOR_SCALARS},
    ]

    def execute(self, inputs):
        tensor = inputs.get('tensor_in')
        if tensor is None:
            raise ValueError("Tensor Scalars: no tensor connected.")
        module = _dmri_module('diffusiontensorscalarmeasurements')
        operation = self.get_property('operation')
        out = _owned(self, 'volume_out', 'vtkMRMLScalarVolumeNode',
                     f"{tensor.GetName()}_{operation}")
        _run_cli(module, {
            'inputVolume': tensor,
            'outputScalar': out,
            'operation': operation,
        }, "Tensor Scalars")
        _finish_outputs(out)
        return {'volume_out': out}

    def route_to_viewer(self):
        out = self._cache.get('volume_out')
        if out is not None:
            _show_volume(out)


# ---------------------------------------------------------------------------
# Tractography
# ---------------------------------------------------------------------------

class TractographyNode(SlicerBaseNode):
    """Seeds streamlines in a tensor volume from a label region."""

    NODE_NAME    = "Tractography"
    CATEGORY     = "Diffusion"
    # Whole-brain seeding takes a while; keep it out of the auto-rerun loop.
    AUTO_EXECUTE = False

    INPUT_PORTS  = [("tensor_in", "Tensor", TENSOR),
                    ("seed_in",   "Seed Region", VOLUME)]
    OUTPUT_PORTS = [("fibers_out", "Fibers", FIBERS)]

    PROPERTIES = [
        {'name': 'seed_label', 'label': 'Seed Label', 'type': 'int',
         'default': 1, 'min': 1, 'max': 100000},
        {'name': 'seed_spacing', 'label': 'Seed Spacing (mm)', 'type': 'float',
         'default': 2.0, 'min': 0.1, 'max': 20.0},
        {'name': 'start_fa', 'label': 'Start FA', 'type': 'float',
         'default': 0.3, 'min': 0.0, 'max': 1.0},
        {'name': 'stop_fa', 'label': 'Stop FA', 'type': 'float',
         'default': 0.25, 'min': 0.0, 'max': 1.0},
        {'name': 'min_length', 'label': 'Minimum Length (mm)', 'type': 'float',
         'default': 20.0, 'min': 0.0, 'max': 1000.0},
        {'name': 'max_length', 'label': 'Maximum Length (mm)', 'type': 'float',
         'default': 800.0, 'min': 1.0, 'max': 2000.0},
    ]

    def execute(self, inputs):
        tensor = inputs.get('tensor_in')
        seed = inputs.get('seed_in')
        if tensor is None:
            raise ValueError("Tractography: no tensor connected.")
        if seed is None:
            raise ValueError("Tractography: no seed region connected.")
        module = _dmri_module('tractographylabelmapseeding')
        fibers = _owned(self, 'fibers_out', 'vtkMRMLFiberBundleNode',
                        tensor.GetName() + '_fibers')
        with _LabelMap(seed) as label:
            _run_cli(module, {
                'InputVolume': tensor,
                'InputROI': label,
                'OutputFibers': fibers,
                'ROIlabel': int(self.get_property('seed_label')),
                'SeedSpacing': float(self.get_property('seed_spacing')),
                'ClTh': float(self.get_property('start_fa')),
                'StoppingValue': float(self.get_property('stop_fa')),
                'MinimumLength': float(self.get_property('min_length')),
                'MaximumLength': float(self.get_property('max_length')),
            }, "Tractography")
        if fibers.GetDisplayNode() is None:
            fibers.CreateDefaultDisplayNodes()
        _finish_outputs(fibers)
        return {'fibers_out': fibers}

    def route_to_viewer(self):
        fibers = self._cache.get('fibers_out')
        if fibers is None:
            return
        for other in slicer.util.getNodesByClass('vtkMRMLFiberBundleNode'):
            for i in range(other.GetNumberOfDisplayNodes()):
                dn = other.GetNthDisplayNode(i)
                if dn is not None and other.GetID() != fibers.GetID():
                    dn.SetVisibility(False)
        dn = fibers.GetDisplayNode()
        if dn is not None:
            dn.SetVisibility(True)
        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView)
        slicer.util.resetThreeDViews()

    def route_fullscreen(self):
        self.route_to_viewer()
        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
        slicer.util.resetThreeDViews()


class TractographyDisplayNode(LinkedModuleNode):
    """Opens the Tractography Display module on the input fibers."""

    NODE_NAME     = "Tractography Display"
    CATEGORY      = "Diffusion"
    LINKED_MODULE = "TractographyDisplay"

    INPUT_PORTS   = [("fibers_in",  "Fibers", FIBERS)]
    OUTPUT_PORTS  = [("fibers_out", "Fibers", FIBERS)]
    INPUT_SETTERS = {'fibers_in': ('setFiberBundleNode',)}

    def route_to_viewer(self):
        fibers = self._cache.get('fibers_in')
        if fibers is None:
            return
        dn = fibers.GetDisplayNode()
        if dn is not None:
            dn.SetVisibility(True)
        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView)


# ---------------------------------------------------------------------------
# Fiber Measurements
# ---------------------------------------------------------------------------

class FiberMeasurementsNode(SlicerBaseNode):
    """Measures a fiber bundle (count, length, FA and other tensor
    scalars along the fibers) into a table."""

    NODE_NAME    = "Fiber Measurements"
    CATEGORY     = "Measure"

    INPUT_PORTS  = [("fibers_in", "Fibers", FIBERS)]
    OUTPUT_PORTS = [("table_out", "Table", TABLE)]

    def execute(self, inputs):
        import shutil
        import tempfile
        import vtk

        fibers = inputs.get('fibers_in')
        if fibers is None:
            raise ValueError("Fiber Measurements: no fibers connected.")
        module = _dmri_module('fibertractmeasurements')

        # The module reads bundles from a folder and writes a text file.
        work = tempfile.mkdtemp(prefix='NodeEditorFibers_')
        try:
            bundle_path = os.path.join(work, 'bundle.vtk')
            writer = vtk.vtkPolyDataWriter()
            writer.SetFileName(bundle_path)
            writer.SetFileTypeToBinary()
            writer.SetInputData(fibers.GetPolyData())
            if not writer.Write():
                raise RuntimeError(
                    "Fiber Measurements: could not write the bundle.")
            out_path = os.path.join(work, 'measurements.txt')
            _run_cli(module, {
                'inputType': 'Fibers_File_Folder',
                'InputDirectory': work,
                'outputFile': out_path,
                'outputFormat': 'Column_Hierarchy',
                'outputSeparator': 'Tab',
            }, "Fiber Measurements")
            with open(out_path) as f:
                rows = [line.rstrip('\n').split('\t')
                        for line in f if line.strip()]
        finally:
            shutil.rmtree(work, ignore_errors=True)
        if len(rows) < 2:
            raise RuntimeError("Fiber Measurements: no measurements returned.")

        table = _owned(self, 'table_out', 'vtkMRMLTableNode',
                       fibers.GetName() + '_measurements')
        table.RemoveAllColumns()
        header = [h.strip() for h in rows[0]]
        for c, title in enumerate(header):
            column = table.AddColumn()
            column.SetName(title or f"Column {c + 1}")
        for row in rows[1:]:
            r = table.AddEmptyRow()
            for c, cell in enumerate(row[:len(header)]):
                text = cell.strip()
                if c == 0:
                    # The first cell is the bundle's temporary file path.
                    text = fibers.GetName()
                table.SetCellText(r, c, text)
        return {'table_out': table}

    def route_to_viewer(self):
        table = self._cache.get('table_out')
        if table is not None:
            from .segment_ops_nodes import _show_table
            _show_table(table)
