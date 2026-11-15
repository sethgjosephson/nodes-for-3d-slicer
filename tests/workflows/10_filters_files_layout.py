# Every Simple Filter, Median, Load Volume and Save Volume, and the Layout
# node.
import os

import numpy as np

g = G(editor)
g.clear()

section("save a small volume, then load it back")
src = g.add('SampleDataNode', x=0, y=0, sample='MRHead')
roi = g.add('NewMarkupNode', x=260, y=0, kind='ROI')
crop = g.add('CropVolumeNode', x=0, y=140)
g.connect(src, 'volume_out', crop, 'volume_in')
g.connect(roi, 'markup_out', crop, 'roi_in')
g.select(roi)
g.press('9')
r = g.out(roi, 'markup_out')
slicer.app.applicationLogic().GetInteractionNode().SetCurrentInteractionMode(
    slicer.vtkMRMLInteractionNode.ViewTransform)
r.SetCenter(0.0, 20.0, 10.0)
r.SetSize(70.0, 70.0, 70.0)
wait(600)
small_path = os.path.join(OUT_DIR, 'small_head.nrrd')
if os.path.exists(small_path):
    os.remove(small_path)
save = g.add('SaveVolumeNode', x=0, y=280, file_path=small_path)
g.connect(crop, 'volume_out', save, 'volume_in')
g.select(save)
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
check(os.path.exists(small_path) and os.path.getsize(small_path) > 1000,
      "Save Volume wrote the file")
saved = array(g.out(crop, 'volume_out')).copy()

g.clear()
wait(300)
load = g.add('LoadVolumeNode', x=0, y=0, file_path=small_path)
g.select(load)
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
loaded = g.out(load, 'volume_out')
check(loaded is not None and (array(loaded) == saved).all(),
      "Load Volume reads back the same voxels")
check(not loaded.GetSaveWithScene(),
      "the loaded volume is marked as graph data")
n_before = len(slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode'))
g.scene.mark_dirty_from(load)
g.select(load)
g.press('1')
check(len(slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode'))
      == n_before, "loading again does not pile up volumes")
loaded = g.out(load, 'volume_out')

section("missing file")
orig = slicer.util.errorDisplay
slicer.util.errorDisplay = lambda *a, **k: None
bad = g.add('LoadVolumeNode', x=520, y=0,
            file_path=os.path.join(OUT_DIR, 'does_not_exist.nrrd'))
down = g.add('GaussianSmoothNode', x=520, y=140)
g.connect(bad, 'volume_out', down, 'volume_in')
try:
    g.select(down)
    g.press('8')
finally:
    slicer.util.errorDisplay = orig
check(g.error(bad) is not None, f"the load error is shown ({g.error(bad)})")
check(down.node_data.is_dirty and g.error(down) is None,
      "the node below it did not run")
g.select(bad, down)
g.press('Del')

section("every Simple Filter")
from Nodes.simple_filter_node import FILTERS
# Canny's thresholds are absolute gradient values; this small crop of
# brain tissue needs lower ones than the defaults.
filt = g.add('SimpleFilterNode', x=0, y=140, canny_lower=1.0, canny_upper=5.0)
g.connect(load, 'volume_out', filt, 'volume_in')
src_arr = array(loaded).astype(float)
for name in FILTERS:
    g.set(filt, 'filter', name)
    g.select(filt)
    g.press('2')
    out = g.out(filt, 'volume_out')
    err = g.error(filt)
    ok = err is None and out is not None
    detail = ""
    if ok:
        a = array(out).astype(float)
        ok = a.shape == src_arr.shape and np.isfinite(a).all() and a.std() > 0
        changed = not np.array_equal(a, src_arr)
        detail = f"std {a.std():.1f}, changed {changed}"
        ok = ok and changed
    check(ok, f"{name}: {detail or err}")
check(len([n for n in slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode')])
      == n_before + 1, "the filter reused one output volume throughout")

section("Median Filter")
med = g.add('MedianFilterNode', x=260, y=140, radius=2)
g.connect(load, 'volume_out', med, 'volume_in')
g.select(med)
g.press('3')
check(g.error(med) is None, f"no error ({g.error(med)})")
check(array(g.out(med, 'volume_out')).astype(float).std() < src_arr.std(),
      "median lowers the spread")

section("Layout node")
layout = g.add('LayoutNode', x=0, y=320)
g.connect(load, 'volume_out', layout, 'red_in')
g.connect(filt, 'volume_out', layout, 'yellow_in')
g.connect(med, 'volume_out', layout, 'green_in')
g.connect(load, 'volume_out', layout, 'render_in')
g.select(layout)
g.press('4')
check(not g.errors(), f"no errors ({g.errors()})")
lm = slicer.app.layoutManager()
check(lm.layout == slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView,
      "four-up layout")


def background(color):
    return slicer.mrmlScene.GetNodeByID(
        f'vtkMRMLSliceCompositeNode{color}').GetBackgroundVolumeID()


check(background('Red') == loaded.GetID(), "red shows the loaded volume")
check(background('Yellow') == g.out(filt, 'volume_out').GetID(),
      "yellow shows the filtered volume")
check(background('Green') == g.out(med, 'volume_out').GetID(),
      "green shows the median volume")
vr = slicer.modules.volumerendering.logic().GetFirstVolumeRenderingDisplayNode(
    loaded)
check(vr is not None and vr.GetVisibility(), "3D shows a volume rendering")
screenshot("layout_four_up")
for name, expected in [
        ('Conventional', slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView),
        ('3D Only', slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView),
        ('Side By Side', slicer.vtkMRMLLayoutNode.SlicerLayoutSideBySideView)]:
    g.set(layout, 'layout', name)
    wait(1200)
    check(lm.layout == expected, f"layout property '{name}' applies")

section("delete the Layout node")
g.select(layout)
g.press('Del')
check(len(slicer.util.getNodesByClass('vtkMRMLVolumeRenderingDisplayNode'))
      == 0, "its volume rendering is removed with it")

g.finish()
