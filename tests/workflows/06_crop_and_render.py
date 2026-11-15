# Crop a CT to a region of interest and volume render the crop.
g = G(editor)
g.clear()

section("CTChest -> Crop Volume -> Volume Rendering")
src = g.add('SampleDataNode', sample='CTChest')
crop = g.add('CropVolumeNode')
vr = g.add('VolumeRenderingNode')
g.chain(src, crop, vr)
g.select(vr)
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
full = g.out(src, 'volume_out')
cropped = g.out(crop, 'volume_out')
check(cropped is not None, "cropped volume exists")
check(array(cropped).shape == array(full).shape,
      "default ROI covers the whole volume")

section("shrink the ROI by hand")
roi = crop.node_data._cache.get('_roi_node')
check(roi is not None, "crop ROI exists")
size = list(roi.GetSize())
roi.SetSize(size[0] / 2, size[1] / 2, size[2] / 2)
wait(1500)
check(not g.dirty(), f"the viewed chain re-ran by itself ({g.dirty()})")
check(not g.errors(), f"no errors ({g.errors()})")
shape_full = array(full).shape
shape_crop = array(g.out(crop, 'volume_out')).shape
print(f"  full {shape_full} cropped {shape_crop}")
check(all(c < f for c, f in zip(shape_crop, shape_full)),
      "the hand-sized ROI is respected on re-run")
dn = vr.node_data._owned_display_node()
check(dn is not None and dn.GetVisibility(), "volume rendering visible")
check(dn.GetDisplayableNode().GetID() == g.out(crop, 'volume_out').GetID(),
      "rendering shows the cropped volume")
screenshot("cropped_vr")

section("double-click Crop Volume opens the module on its parameters")
editor._on_node_selected(crop)
wait(500)
check(slicer.util.selectedModule() == 'CropVolume',
      f"Crop Volume module shown ({slicer.util.selectedModule()})")
slicer.util.selectModule('SlicerNodeEditor')
wait(300)
check(all(c < f for c, f in zip(
    array(g.out(crop, 'volume_out')).shape, shape_full)),
      "opening the module did not reset the crop")

section("disable the crop: rendering switches to the full volume")
dn_id = dn.GetID()
g.select(crop)
g.press('D')
wait(1500)
dn2 = vr.node_data._owned_display_node()
check(dn2 is not None and dn2.GetID() == dn_id,
      "same display node after the switch")
check(dn2.GetDisplayableNode().GetID() == full.GetID(),
      "rendering shows the full volume")

section("F on the rendering node")
g.select(vr)
g.press('F')
check(slicer.app.layoutManager().layout
      == slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView, "3D only layout")
screenshot("vr_fullscreen")

g.finish()
