# Two timepoints of a brain tumor: register, resample onto one grid, subtract, and carry a label volume across with the same transform.
import numpy as np

g = G(editor)
g.clear()


def corr(a, b):
    return float(np.corrcoef(a.ravel().astype(float),
                             b.ravel().astype(float))[0, 1])


section("build")
t1 = g.add('SampleDataNode', x=-260, y=0, sample='MRBrainTumor1')
t2 = g.add('SampleDataNode', x=260, y=0, sample='MRBrainTumor2')
reg = g.add('RegistrationNode', x=0, y=150, type='Rigid', sampling=0.02)
g.connect(t1, 'volume_out', reg, 'fixed_in')
g.connect(t2, 'volume_out', reg, 'moving_in')
res = g.add('ResampleVolumeNode', x=260, y=300)
g.connect(t2, 'volume_out', res, 'volume_in')
g.connect(t1, 'volume_out', res, 'reference_in')
g.connect(reg, 'transform_out', res, 'transform_in')
diff = g.add('VolumeMathNode', x=0, y=450, operation='A - B')
g.connect(res, 'volume_out', diff, 'a_in')
g.connect(t1, 'volume_out', diff, 'b_in')

section("view the difference")
g.select(diff)
g.press('1', timeout_s=900)
wait(2000)
check(not g.errors(), f"no errors ({g.errors()})")
check(not g.dirty(), f"the whole graph ran ({g.dirty()})")
fixed = array(g.out(t1, 'volume_out'))
moving = array(g.out(t2, 'volume_out'))
resampled = array(g.out(res, 'volume_out'))
brainsfit = array(g.out(reg, 'registered_out'))
check(resampled.shape == fixed.shape, "resampled volume is on the fixed grid")
c_node = corr(resampled, brainsfit)
print(f"  Resample Volume vs BRAINSFit output: r = {c_node:.4f}")
check(c_node > 0.98,
      "resampling with the transform reproduces the BRAINSFit result")
c_fixed = corr(resampled, fixed)
print(f"  resampled vs fixed: r = {c_fixed:.3f}")
check(c_fixed > 0.5, "the resampled volume lines up with the fixed volume")
d = array(g.out(diff, 'volume_out'))
check(d.shape == fixed.shape and d.min() < 0 < d.max(),
      "the difference has both signs")
check(np.allclose(d, resampled.astype(np.float32) - fixed.astype(np.float32)),
      "the difference is A minus B voxel for voxel")
check(g.out(t2, 'volume_out').GetParentTransformNode() is None,
      "the moving volume was not moved")
check((array(g.out(t2, 'volume_out')) == moving).all(),
      "the moving volume's voxels are unchanged")
screenshot("difference")

section("without the transform the two do not line up as well")
g.scene.capture_undo()
edge = g.scene.get_incoming_edge(res.get_port('transform_in', is_input=True))
g.scene.remove_edge(edge)
g.scene.mark_dirty_from(res)
g.select(diff)
g.press('1')
c_plain = corr(array(g.out(res, 'volume_out')), fixed)
print(f"  resampled without transform vs fixed: r = {c_plain:.3f}")
check(c_plain < c_fixed, "registration improves the match")
g.press('Z', ctrl=True)
g.select(g.by_name('Volume Math'))
g.press('1', timeout_s=900)
wait(1500)
check(not g.dirty(), f"clean after undo ({g.dirty()})")
check(len(slicer.util.getNodesByClass('vtkMRMLCommandLineModuleNode')) == 1,
      "undo did not start a second registration")

section("carry a label volume across with the same transform")
t2 = g.by_name('Sample Data', 1)
reg = g.by_name('Registration')
t1 = g.by_name('Sample Data', 0)
labels = g.add('ThresholdNode', x=520, y=150, mode='Binary mask',
               lower=200.0, upper=5000.0, inside=7)
g.connect(t2, 'volume_out', labels, 'volume_in')
lab_res = g.add('ResampleVolumeNode', x=520, y=300,
                interpolation='Nearest Neighbor')
g.connect(labels, 'volume_out', lab_res, 'volume_in')
g.connect(t1, 'volume_out', lab_res, 'reference_in')
g.connect(reg, 'transform_out', lab_res, 'transform_in')
to_seg = g.add('LabelMapToSegmentationNode', x=520, y=450)
g.connect(lab_res, 'volume_out', to_seg, 'volume_in')
g.select(to_seg)
g.press('2')
check(not g.errors(), f"no errors ({g.errors()})")
lab = array(g.out(lab_res, 'volume_out'))
check(set(np.unique(lab).tolist()) <= {0, 7},
      f"nearest neighbor keeps label values ({np.unique(lab).tolist()})")
check(lab.shape == fixed.shape, "labels are on the fixed grid")
seg = g.out(to_seg, 'seg_out')
check(seg.GetSegmentation().GetNumberOfSegments() == 1,
      "one segment from the carried label")
check(len(slicer.util.getNodesByClass('vtkMRMLCommandLineModuleNode')) == 1,
      "one transform served both branches without a second registration")

import os
g.save(os.path.join(OUT_DIR, 'longitudinal.json'))

section("every math operation")
from Nodes.resample_nodes import MATH_OPERATIONS
diff = g.by_name('Volume Math')
for name in MATH_OPERATIONS:
    g.set(diff, 'operation', name)
    g.select(diff)
    g.press('1')
    check(g.error(diff) is None and np.isfinite(
        array(g.out(diff, 'volume_out'))).all(), f"{name}")

section("mismatched grids are refused")
bad = g.add('VolumeMathNode', x=-260, y=450)
g.connect(t1, 'volume_out', bad, 'a_in')
g.connect(t2, 'volume_out', bad, 'b_in')
orig = slicer.util.errorDisplay
slicer.util.errorDisplay = lambda *a, **k: None
try:
    g.select(bad)
    g.press('3')
finally:
    slicer.util.errorDisplay = orig
check(g.error(bad) is not None and 'Resample' in g.error(bad),
      f"clear message ({g.error(bad)})")

g.finish()
