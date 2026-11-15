# A filter chain on MRHead, edited the way a person edits it:
# property changes, disable, delete with splice, undo, copy and paste.
g = G(editor)
g.clear()

section("build: Sample Data -> Gaussian -> Threshold -> Volumes")
src = g.add('SampleDataNode', sample='MRHead')
smooth = g.add('GaussianSmoothNode', sigma=2.0)
thresh = g.add('ThresholdNode', lower=40.0, upper=200.0)
vols = g.add('VolumesNode')
g.chain(src, smooth, thresh, vols)
check(len(g.scene._edges) == 3, "three edges after auto-connect")

g.select(vols)
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
wait(400)
check(not g.dirty(), f"nothing dirty after viewing ({g.dirty()})")
src_vol = g.out(src, 'volume_out')
smooth_vol = g.out(smooth, 'volume_out')
thresh_vol = g.out(thresh, 'volume_out')
check(src_vol is not None and smooth_vol is not None
      and thresh_vol is not None, "all three volumes exist")
check(len({src_vol.GetID(), smooth_vol.GetID(), thresh_vol.GetID()}) == 3,
      "each node owns its own volume")
a_src = array(src_vol).astype(float)
a_smooth = array(smooth_vol).astype(float)
check(a_smooth.std() < a_src.std(), "smoothing lowers the spread")
a_thresh = array(thresh_vol)
inside = a_thresh[a_thresh != 0]
check(inside.size > 0 and inside.min() >= 40 and inside.max() <= 200,
      "threshold keeps only values in range")
src_before = a_src.copy()
screenshot("chain_viewed")

section("property change re-runs the viewed chain")
count_before = int((a_thresh != 0).sum())
g.set(thresh, 'lower', 100.0)
g.scene.notify_property_changed(thresh)
wait(1200)
check(not thresh.node_data.is_dirty, "threshold re-ran by itself")
count_after = int((array(g.out(thresh, 'volume_out')) != 0).sum())
check(count_after < count_before,
      f"fewer voxels kept after raising lower ({count_before} -> {count_after})")
check(g.out(thresh, 'volume_out').GetID() == thresh_vol.GetID(),
      "threshold reused its output volume")
check(g.out(src, 'volume_out').GetID() == src_vol.GetID(),
      "sample data was not downloaded again")

section("disable the smoothing node (D)")
g.select(smooth)
g.press('D')
wait(1200)
check(smooth.node_data.is_disabled, "smooth is disabled")
check(g.out(smooth, 'volume_out').GetID() == src_vol.GetID(),
      "disabled smooth passes the source volume through")
check(not g.dirty(), f"chain re-ran after disable ({g.dirty()})")
check((array(src_vol) == src_before).all(), "source volume untouched")
g.press('D')
wait(1200)
check(not smooth.node_data.is_disabled, "smooth enabled again")
check(g.out(smooth, 'volume_out').GetID() == smooth_vol.GetID(),
      "enabled smooth returns to its own volume")
check((array(src_vol) == src_before).all(),
      "source volume untouched after re-enable")
check(abs(array(smooth_vol).astype(float).std() - a_smooth.std()) < 1e-6,
      "smoothing applied once, not twice")

section("delete the smoothing node: edge is spliced")
g.select(smooth)
g.press('Del')
check(len(g.scene.all_node_items()) == 3, "three nodes left")
check(len(g.scene._edges) == 2, "two edges left (spliced)")
g.select(vols)
g.press('1')
check(not g.errors(), f"no errors after splice ({g.errors()})")
unsmoothed = int((array(g.out(thresh, 'volume_out')) != 0).sum())
check(unsmoothed != count_after, "threshold now works on unsmoothed data")
check(not mrml_exists(smooth_vol),
      "deleted node's volume was removed from the scene")

section("undo brings the node and edges back")
g.press('Z', ctrl=True)
names = sorted(ni.node_data.NODE_NAME for ni in g.scene.all_node_items())
check(names == ['Gaussian Smooth', 'Sample Data', 'Threshold', 'Volumes'],
      f"four nodes after undo ({names})")
check(len(g.scene._edges) == 3, "three edges after undo")
smooth2 = g.by_name('Gaussian Smooth')
check(float(smooth2.node_data.get_property('sigma')) == 2.0,
      "sigma survived undo")
g.select(g.by_name('Volumes'))
g.press('1')
check(not g.errors(), f"no errors after undo ({g.errors()})")
check(not g.dirty(), f"nothing dirty after undo and view ({g.dirty()})")
g.press('Y', ctrl=True)
check(len(g.scene.all_node_items()) == 3, "redo removes the node again")
g.press('Z', ctrl=True)
check(len(g.scene.all_node_items()) == 4, "undo again restores it")

section("copy and paste a node")
t = g.by_name('Threshold')
g.select(t)
g.press('C', ctrl=True)
g.press('V', ctrl=True)
threshes = [ni for ni in g.scene.all_node_items()
            if ni.node_data.NODE_NAME == 'Threshold']
check(len(threshes) == 2, "two threshold nodes after paste")
if len(threshes) == 2:
    check(float(threshes[1].node_data.get_property('lower'))
          == float(threshes[0].node_data.get_property('lower')),
          "pasted node carries the property values")

section("fullscreen (F)")
g.select(g.by_name('Threshold'))
g.press('F')
lm = slicer.app.layoutManager()
check(lm.layout == slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView,
      "F shows a single slice view")
screenshot("fullscreen_threshold")

g.finish()
