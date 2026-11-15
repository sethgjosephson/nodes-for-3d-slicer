# The bundled demo graph: three pipelines, each viewed with a viewer key.
import qt

g = G(editor)

section("load demo")
editor._on_load_demo()
wait(300)
items = g.scene.all_node_items()
check(len(items) == 8, f"demo has 8 nodes (got {len(items)})")
check(len(g.scene._edges) == 5, f"demo has 5 edges (got {len(g.scene._edges)})")

section("column A: MRHead -> Volume Rendering")
vr_a = g.by_name("Volume Rendering", 0)
g.select(vr_a)
g.press('1')
check(not g.errors(), f"no node errors ({g.errors()})")
check(not vr_a.node_data.is_dirty, "VR node is clean")
dn = vr_a.node_data._owned_display_node()
check(dn is not None and dn.GetVisibility(), "VR display node visible")
screenshot("A_mrhead_vr")

section("column B: CTChest -> Gaussian -> Volume Rendering")
vr_b = g.by_name("Volume Rendering", 1)
g.select(vr_b)
g.press('2')
check(not g.errors(), f"no node errors ({g.errors()})")
smooth = g.by_name("Gaussian Smooth")
out = g.out(smooth, 'volume_out')
check(out is not None and array(out).std() > 0, "smoothed CT has data")
dn_b = vr_b.node_data._owned_display_node()
check(dn_b is not None and dn_b.GetVisibility(), "second VR visible")
check(not dn.GetVisibility(), "first VR hidden while the second is shown")
screenshot("B_ctchest_smooth_vr")

section("column C: MRHead -> Threshold -> Volumes")
vols = g.by_name("Volumes")
g.select(vols)
g.press('3')
check(not g.errors(), f"no node errors ({g.errors()})")
thresh = g.by_name("Threshold")
tout = g.out(thresh, 'volume_out')
check(tout is not None, "threshold output exists")
red = slicer.mrmlScene.GetNodeByID('vtkMRMLSliceCompositeNodeRed')
check(tout is not None and red.GetBackgroundVolumeID() == tout.GetID(),
      "red slice shows the threshold output")
screenshot("C_threshold_slices")

section("back to slot 1 with nothing selected")
g.select()
g.press('1')
check(dn.GetVisibility(), "first VR visible again")
check(not dn_b.GetVisibility(), "second VR hidden again")

section("execute all")
editor._on_execute_all()
wait(300)
dirty = [ni.node_data.NODE_NAME for ni in g.scene.all_node_items()
         if ni.node_data.is_dirty]
check(not dirty, f"no dirty nodes after Execute All ({dirty})")

g.finish()
