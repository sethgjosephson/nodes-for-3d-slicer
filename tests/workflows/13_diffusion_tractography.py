# extensions: SlicerDMRI The diffusion MRI pipeline: DWI -> mask -> tensor -> FA and MD -> tractography -> fiber measurements.
import os

import numpy as np

g = G(editor)
g.clear()

section("build")
dwi = g.add('SampleDWINode', x=0, y=0)
mask = g.add('DWIMaskNode', x=260, y=130)
tensor = g.add('TensorEstimationNode', x=0, y=260)
g.connect(dwi, 'dwi_out', mask, 'dwi_in')
g.connect(dwi, 'dwi_out', tensor, 'dwi_in')
g.connect(mask, 'mask_out', tensor, 'mask_in')
fa = g.add('TensorScalarsNode', x=-260, y=400,
           operation='FractionalAnisotropy')
md = g.add('TensorScalarsNode', x=0, y=400, operation='MeanDiffusivity')
g.connect(tensor, 'tensor_out', fa, 'tensor_in')
g.connect(tensor, 'tensor_out', md, 'tensor_in')
check(g.scene.connect_ports(dwi.get_port('dwi_out', is_input=False),
                            fa.get_port('tensor_in', is_input=True)) is None,
      "a DWI cannot be connected to a tensor input")
smooth = g.add('GaussianSmoothNode', x=520, y=0)
check(g.scene.connect_ports(dwi.get_port('dwi_out', is_input=False),
                            smooth.get_port('volume_in', is_input=True))
      is None, "a DWI cannot be connected to a scalar volume filter")
g.select(smooth)
g.press('Del')

section("FA map")
g.select(fa)
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
dwi_node = g.out(dwi, 'dwi_out')
check(dwi_node is not None and dwi_node.IsA(
    'vtkMRMLDiffusionWeightedVolumeNode'), "sample is a DWI node")
print(f"  DWI gradients: {dwi_node.GetNumberOfGradients()}")
mask_node = g.out(mask, 'mask_out')
m = array(mask_node)
frac = float((m > 0).mean())
print(f"  mask covers {frac:.2f} of the volume")
check(0.05 < frac < 0.9, "the mask is a plausible brain region")
t = g.out(tensor, 'tensor_out')
check(t is not None and t.IsA('vtkMRMLDiffusionTensorVolumeNode'),
      "tensor volume exists")
fa_arr = array(g.out(fa, 'volume_out')).astype(float)
check(fa_arr.shape == m.shape, "FA is on the DWI grid")
red = slicer.mrmlScene.GetNodeByID('vtkMRMLSliceCompositeNodeRed')
check(red.GetBackgroundVolumeID() == g.out(fa, 'volume_out').GetID(),
      "the slice views show the FA map that is being viewed")
check(red.GetLabelVolumeID() is None,
      "the mask was not pushed into the slice views by its module")
inside = fa_arr[m > 0]
print(f"  FA inside the mask: mean {inside.mean():.3f}, max {inside.max():.3f}")
check(0.0 <= fa_arr.min() and inside.max() <= 1.2,
      "FA values are in range")
check(0.1 < inside.mean() < 0.6, "mean FA in the brain is plausible")
check(float(np.abs(fa_arr[m == 0]).max()) == 0.0,
      "FA is zero outside the mask")
screenshot("fa_map")

section("MD map from the same tensor: one fit, two consumers")
g.select(md)
g.press('2')
check(not g.errors(), f"no errors ({g.errors()})")
md_arr = array(g.out(md, 'volume_out')).astype(float)
print(f"  MD inside the mask: mean {md_arr[m > 0].mean():.6f}")
check(md_arr[m > 0].mean() > 0, "mean diffusivity is positive in the brain")
check(g.out(tensor, 'tensor_out').GetID() == t.GetID()
      and not tensor.node_data.is_dirty,
      "the tensor was fitted once and reused")

section("change the measure on one branch")
g.set(md, 'operation', 'Trace')
wait(4000)
trace = array(g.out(md, 'volume_out')).astype(float)
check(np.allclose(trace[m > 0].mean(), 3.0 * md_arr[m > 0].mean(),
                  rtol=0.02),
      "trace is three times the mean diffusivity")

section("tractography seeded from high FA")
seeds = g.add('ThresholdNode', x=-260, y=540, mode='Binary mask',
              lower=0.45, upper=1.5, inside=1)
g.connect(fa, 'volume_out', seeds, 'volume_in')
tract = g.add('TractographyNode', x=-130, y=680, seed_spacing=3.0,
              min_length=30.0)
g.connect(tensor, 'tensor_out', tract, 'tensor_in')
g.connect(seeds, 'volume_out', tract, 'seed_in')
view = g.add('TractographyDisplayNode', x=-260, y=820)
g.connect(tract, 'fibers_out', view, 'fibers_in')
g.select(view)
g.press('3', timeout_s=900)
check(not g.errors(), f"no errors ({g.errors()})")
fibers = g.out(tract, 'fibers_out')
n_fibers = fibers.GetPolyData().GetNumberOfLines() if fibers else 0
print(f"  fibers: {n_fibers}")
check(n_fibers > 50, "tractography produced fibers")
check(g.out(view, 'fibers_out') is not None
      and g.out(view, 'fibers_out').GetID() == fibers.GetID(),
      "Tractography Display passes the fibers on")
check(len(slicer.util.getNodesByClass('vtkMRMLLabelMapVolumeNode')) == 1,
      "no temporary label maps left behind (only the mask)")
check(len(slicer.util.getNodesByClass('vtkMRMLCommandLineModuleNode')) == 0,
      "no command line module nodes left behind")
screenshot("tractography")

section("a longer minimum length gives fewer fibers")
g.set(tract, 'min_length', 80.0)
check('Tractography' in g.dirty(), "tractography waits for a key press")
g.select(view)
g.press('3', timeout_s=900)
n_long = g.out(tract, 'fibers_out').GetPolyData().GetNumberOfLines()
print(f"  fibers at 80 mm minimum: {n_long}")
check(0 < n_long < n_fibers, "fewer fibers with a longer minimum")
check(g.out(tract, 'fibers_out').GetID() == fibers.GetID(),
      "the fiber bundle node is reused")

section("fiber measurements")
meas = g.add('FiberMeasurementsNode', x=130, y=820)
g.connect(tract, 'fibers_out', meas, 'fibers_in')
g.select(meas)
g.press('4')
check(not g.errors(), f"no errors ({g.errors()})")
table = g.out(meas, 'table_out')
check(table is not None and table.GetNumberOfRows() == 1,
      "one row for the bundle")
cols = [table.GetColumnName(i) for i in range(table.GetNumberOfColumns())]
print(f"  columns: {cols}")
row = {c: table.GetCellText(0, i) for i, c in enumerate(cols)}
print(f"  row: {row}")
count_cols = [c for c in cols if 'Num_Fibers' in c or 'Fibers' in c]
check(bool(count_cols), "the table has a fiber count")
if count_cols:
    check(int(float(row[count_cols[0]])) == n_long,
          f"fiber count matches the bundle ({row[count_cols[0]]})")
screenshot("fiber_measurements")

section("export and reload")
csv_path = os.path.join(OUT_DIR, 'fiber_measurements.csv')
fa_path = os.path.join(OUT_DIR, 'fa.nrrd')
for p in (csv_path, fa_path):
    if os.path.exists(p):
        os.remove(p)
s1 = g.add('SaveDataNode', x=130, y=960, file_path=csv_path)
g.connect(meas, 'table_out', s1, 'data_in')
s2 = g.add('SaveVolumeNode', x=-520, y=540, file_path=fa_path)
g.connect(fa, 'volume_out', s2, 'volume_in')
g.select(s1)
g.press('5')
g.select(s2)
g.press('6')
check(os.path.exists(csv_path) and os.path.getsize(csv_path) > 0,
      "measurements written")
check(os.path.exists(fa_path) and os.path.getsize(fa_path) > 1000,
      "FA map written")
graph = g.save(os.path.join(OUT_DIR, 'diffusion.json'))
n_nodes = len(g.scene.all_node_items())
editor._on_clear()
wait(300)
left = [n.GetName() for n in slicer.util.getNodesByClass('vtkMRMLVolumeNode')]
check(not left, f"Clear removed every volume ({left})")
check(len(slicer.util.getNodesByClass('vtkMRMLFiberBundleNode')) == 0,
      "Clear removed the fibers")
g.load(graph)
check(len(g.scene.all_node_items()) == n_nodes, "graph loaded")
g.select(g.by_name('Fiber Measurements'))
g.press('1', timeout_s=900)
check(not g.errors(), f"no errors ({g.errors()})")
t2 = g.out(g.by_name('Fiber Measurements'), 'table_out')
check(t2 is not None and t2.GetNumberOfRows() == 1,
      "the loaded graph ran through to the measurements")
n_again = g.out(g.by_name('Tractography'),
                'fibers_out').GetPolyData().GetNumberOfLines()
check(n_again == n_long, f"same fiber count as before ({n_again})")

g.finish()
