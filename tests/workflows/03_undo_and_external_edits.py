# Undo keeps computed data, deleting releases it, and an edit made outside
# the graph marks the right nodes dirty.
import numpy as np

g = G(editor)
g.clear()


def auto_nodes():
    """Names of volumes in the scene."""
    return sorted(n.GetName() for n in
                  slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode'))


section("build and view")
src = g.add('SampleDataNode', sample='MRHead')
smooth = g.add('GaussianSmoothNode', sigma=1.5)
thresh = g.add('ThresholdNode', lower=40.0, upper=200.0)
g.chain(src, smooth, thresh)
g.select(thresh)
g.press('1')
check(not g.dirty(), f"clean after view ({g.dirty()})")
src_id = g.out(src, 'volume_out').GetID()
smooth_id = g.out(smooth, 'volume_out').GetID()
check(len(auto_nodes()) == 3, f"three volumes in the scene ({auto_nodes()})")

section("add a node, then undo: computed data is kept")
g.scene.capture_undo()
med = g.add('MedianFilterNode')
g.chain(g.by_name('Threshold'), med)
g.select(med)
g.press('2')
check(len(auto_nodes()) == 4, f"four volumes after median ({auto_nodes()})")
g.press('Z', ctrl=True)
check(len(g.scene.all_node_items()) == 3, "median node gone after undo")
check(len(auto_nodes()) == 3,
      f"median volume released by undo ({auto_nodes()})")
check(not g.dirty(), f"remaining nodes still clean ({g.dirty()})")
check(g.out(g.by_name('Sample Data'), 'volume_out').GetID() == src_id,
      "sample volume is the same MRML node")
check(g.out(g.by_name('Gaussian Smooth'), 'volume_out').GetID() == smooth_id,
      "smoothed volume is the same MRML node")

section("disable, then undo: only the changed branch is dirty")
g.select(g.by_name('Gaussian Smooth'))
g.press('D')
wait(1200)
g.press('Z', ctrl=True)
wait(300)
check(not g.by_name('Gaussian Smooth').node_data.is_disabled,
      "undo re-enabled the node")
check('Sample Data' not in g.dirty(), "sample data stays clean")
check('Gaussian Smooth' in g.dirty() and 'Threshold' in g.dirty(),
      f"smooth and threshold are dirty ({g.dirty()})")
g.select(g.by_name('Threshold'))
g.press('1')
check(not g.dirty(), "clean after viewing again")
check(len(auto_nodes()) == 3, f"still three volumes ({auto_nodes()})")

section("external edit of an intermediate volume")
smooth_vol = g.out(g.by_name('Gaussian Smooth'), 'volume_out')
smooth_vol.SetName('renamed_by_user')
wait(400)
check(not g.dirty(), f"a rename does not mark anything dirty ({g.dirty()})")
arr = slicer.util.arrayFromVolume(smooth_vol)
arr[:] = 0
slicer.util.arrayFromVolumeModified(smooth_vol)
wait(400)
check(g.dirty() == ['Threshold'],
      f"editing the voxels marks only the downstream node ({g.dirty()})")
g.select(g.by_name('Threshold'))
g.press('1')
out = array(g.out(g.by_name('Threshold'), 'volume_out'))
check(int((out != 0).sum()) == 0, "threshold re-ran on the edited voxels")

section("moving a volume under a transform")
xfm = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
smooth_vol.SetAndObserveTransformNodeID(xfm.GetID())
wait(400)
check(g.dirty() == ['Threshold'],
      f"a new parent transform marks the downstream node ({g.dirty()})")
smooth_vol.SetAndObserveTransformNodeID(None)
slicer.mrmlScene.RemoveNode(xfm)

section("clear releases everything")
editor._on_clear()
wait(300)
check(auto_nodes() == [], f"no volumes left after Clear ({auto_nodes()})")
check(len(slicer.util.getNodesByClass('vtkMRMLVolumeRenderingDisplayNode'))
      == 0, "no volume rendering nodes left")

g.finish()
