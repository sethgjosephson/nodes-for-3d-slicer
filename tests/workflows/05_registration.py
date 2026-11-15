# Register two brain MR timepoints, reuse the transform on another volume.
import os
import time

import numpy as np
import vtk

g = G(editor)
g.clear()


def cli_count():
    return len(slicer.util.getNodesByClass('vtkMRMLCommandLineModuleNode'))


section("build")
fixed = g.add('SampleDataNode', x=-200, y=0, sample='MRBrainTumor1')
moving = g.add('SampleDataNode', x=200, y=0, sample='MRBrainTumor2')
reg = g.add('RegistrationNode', x=0, y=160, type='Rigid', sampling=0.02)
g.connect(fixed, 'volume_out', reg, 'fixed_in')
g.connect(moving, 'volume_out', reg, 'moving_in')
smooth = g.add('GaussianSmoothNode', x=300, y=160, sigma=1.0)
g.connect(moving, 'volume_out', smooth, 'volume_in')
apply = g.add('ApplyTransformNode', x=200, y=320, harden=True)
g.connect(smooth, 'volume_out', apply, 'volume_in')
g.connect(reg, 'transform_out', apply, 'transform_in')
xf = g.add('TransformsNode', x=-200, y=320)
g.connect(reg, 'transform_out', xf, 'transform_in')

section("view Apply Transform: registration runs in the background")
t0 = time.time()
g.router.assign_and_activate(apply, 1)
check(getattr(reg.node_data, '_async_pending', False),
      "registration is pending right after the key press")
check(apply.node_data.is_dirty and g.out(apply, 'volume_out') is None,
      "Apply Transform waits for the registration")
g.wait_async(900)
wait(1500)
print(f"  registration took {time.time() - t0:.0f} s")
check(not g.errors(), f"no errors ({g.errors()})")
check(not reg.node_data.is_dirty, "registration is clean")
check(not apply.node_data.is_dirty,
      "Apply Transform ran by itself when the registration finished")
xfm = g.out(reg, 'transform_out')
m = vtk.vtkMatrix4x4()
xfm.GetMatrixTransformToParent(m)
ident = all(abs(m.GetElement(r, c) - (1.0 if r == c else 0.0)) < 1e-6
            for r in range(4) for c in range(4))
check(not ident, "the transform is not the identity")
registered = g.out(reg, 'registered_out')
f = array(g.out(fixed, 'volume_out')).astype(float)
r = array(registered).astype(float)
check(r.shape == f.shape, f"registered volume is on the fixed grid ({r.shape})")
c_after = float(np.corrcoef(f.ravel(), r.ravel())[0, 1])
print(f"  correlation with fixed after registration: {c_after:.3f}")
check(c_after > 0.5, "registered volume correlates with the fixed volume")
out = g.out(apply, 'volume_out')
check(out is not None and out.GetParentTransformNode() is None,
      "hardened output has no parent transform")
check(g.out(smooth, 'volume_out').GetParentTransformNode() is None,
      "the input of Apply Transform was not moved")
screenshot("registered")

section("Transforms wrapper")
g.select(xf)
g.press('2')
check(g.out(xf, 'transform_out') is not None
      and g.out(xf, 'transform_out').GetID() == xfm.GetID(),
      "Transforms node passes the transform on")

section("viewing again does not re-register")
n_cli = cli_count()
g.select(apply)
g.press('1')
check(cli_count() == n_cli, "no new BRAINSFit run")

section("a change beside the registration does not re-run it")
g.set(smooth, 'sigma', 2.0)
g.select(apply)
g.press('1')
check(cli_count() == n_cli, "smoothing change did not start BRAINSFit")
check(not g.dirty(), f"all clean ({g.dirty()})")

section("save graph, clear, load, run again")
path = g.save(os.path.join(OUT_DIR, 'registration.json'))
editor._on_clear()
wait(300)
check(len(slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode')) == 0,
      "Clear removed every volume")
check(cli_count() == 0, "Clear removed the BRAINSFit nodes")
g.load(path)
check(len(g.scene.all_node_items()) == 6 and len(g.scene._edges) == 6,
      "graph loaded with 6 nodes and 6 edges")
reg2 = g.by_name('Registration')
check(float(reg2.node_data.get_property('sampling')) == 0.02,
      "registration settings loaded")
g.select(g.by_name('Apply Transform'))
g.press('1', timeout_s=900)
wait(1500)
check(not g.errors(), f"no errors ({g.errors()})")
check(not g.by_name('Apply Transform').node_data.is_dirty,
      "loaded graph ran to the end")

g.finish()
