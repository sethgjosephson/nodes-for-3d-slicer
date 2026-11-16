# A hand-placed ROI drives a crop, and the graph survives JSON and .mrb round trips with the placement intact.
import os

g = G(editor)
g.clear()


def volumes():
    return slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode')


section("New Markup (ROI) -> Crop Volume")
src = g.add('SampleDataNode', x=0, y=0, sample='MRHead')
roi_node = g.add('NewMarkupNode', x=260, y=0, kind='ROI', name='Crop box')
crop = g.add('CropVolumeNode', x=0, y=160)
g.connect(src, 'volume_out', crop, 'volume_in')
g.connect(roi_node, 'markup_out', crop, 'roi_in')
check(g.scene.connect_ports(src.get_port('volume_out', is_input=False),
                            crop.get_port('roi_in', is_input=True)) is None,
      "a volume cannot be connected to the ROI input")

orig = slicer.util.errorDisplay
slicer.util.errorDisplay = lambda *a, **k: None
try:
    g.select(crop)
    g.press('1')
finally:
    slicer.util.errorDisplay = orig
check(g.error(crop) is not None and 'not been placed' in g.error(crop),
      f"an unplaced ROI gives a clear error ({g.error(crop)})")

section("viewing the markup node starts placement")
g.select(roi_node)
g.press('2')
roi = g.out(roi_node, 'markup_out')
check(roi is not None and roi.IsA('vtkMRMLMarkupsROINode'), "ROI node exists")
check(roi.GetName() == 'Crop box', "the markup carries the node's name")
interaction = slicer.app.applicationLogic().GetInteractionNode()
check(interaction.GetCurrentInteractionMode() == interaction.Place,
      "Slicer is in place mode for the empty markup")
interaction.SetCurrentInteractionMode(interaction.ViewTransform)

section("place the ROI, as a click and drag in a view would")
roi.SetCenter(0.0, 20.0, 10.0)
roi.SetSize(80.0, 90.0, 60.0)
wait(800)
check(roi_node.node_data.get_property('points'),
      "the placement is stored in the node's properties")
check(roi_node.node_data.get_property('roi_size') == [80.0, 90.0, 60.0],
      "the ROI size is stored in the node's properties")
g.select(crop)
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
full_shape = array(g.out(src, 'volume_out')).shape
crop_shape = array(g.out(crop, 'volume_out')).shape
print(f"  full {full_shape} cropped {crop_shape}")
check(all(c < f for c, f in zip(crop_shape, full_shape)),
      "the crop follows the placed ROI")
check(len(slicer.util.getNodesByClass('vtkMRMLMarkupsROINode')) == 1,
      "Crop Volume did not create an ROI of its own")

section("moving the ROI re-runs the viewed crop")
roi.SetSize(40.0, 40.0, 40.0)
wait(1500)
smaller = array(g.out(crop, 'volume_out')).shape
print(f"  cropped {smaller}")
check(all(s < c for s, c in zip(smaller, crop_shape)),
      "the crop shrank with the ROI without a key press")
check(not g.dirty(), f"nothing left dirty ({g.dirty()})")
screenshot("roi_crop")

section("Markups wrapper opens the module on the ROI")
mk = g.add('MarkupsNode', x=260, y=160)
g.connect(roi_node, 'markup_out', mk, 'markup_in')
g.select(mk)
g.press('3')
editor._on_node_selected(mk)
wait(500)
check(slicer.util.selectedModule() == 'Markups', "Markups module shown")
mw = slicer.modules.markups.widgetRepresentation()
tree = [w for w in mw.findChildren('qMRMLSubjectHierarchyTreeView')
        if w.objectName == 'activeMarkupTreeView'][0]
check(tree.currentNode() is not None
      and tree.currentNode().GetID() == roi.GetID(),
      "Markups module shows the ROI")
slicer.util.selectModule('SlicerNodeEditor')
wait(300)

section("JSON round trip keeps the placement")
json_path = g.save(os.path.join(OUT_DIR, 'roi_crop.json'))
editor._on_clear()
wait(300)
check(len(volumes()) == 0 and len(
    slicer.util.getNodesByClass('vtkMRMLMarkupsROINode')) == 0,
      "Clear removed the volumes and the ROI")
g.load(json_path)
g.select(g.by_name('Crop Volume'))
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
check(array(g.out(g.by_name('Crop Volume'), 'volume_out')).shape == smaller,
      "the loaded graph gives the same crop")
roi2 = g.out(g.by_name('New Markup'), 'markup_out')
check([round(v, 3) for v in roi2.GetSize()] == [40.0, 40.0, 40.0],
      "the ROI came back at its saved size")

section("undo after moving the ROI")
g.scene.capture_undo()
roi2.SetSize(100.0, 100.0, 100.0)
wait(1500)
bigger = array(g.out(g.by_name('Crop Volume'), 'volume_out')).shape
check(all(b > s for b, s in zip(bigger, smaller)), "the crop grew")
g.press('Z', ctrl=True)
wait(300)
g.select(g.by_name('Crop Volume'))
g.press('1')
check(array(g.out(g.by_name('Crop Volume'), 'volume_out')).shape == smaller,
      "undo put the ROI and the crop back")

section(".mrb round trip")
mrb_path = os.path.join(OUT_DIR, 'roi_crop.mrb')
if os.path.exists(mrb_path):
    os.remove(mrb_path)
wait(800)   # let the graph sync into the scene
check(slicer.util.saveScene(mrb_path), "scene saved")
print(f"  .mrb size {os.path.getsize(mrb_path)} bytes")
check(os.path.getsize(mrb_path) < 2_000_000,
      "the .mrb does not carry the graph's computed volumes")
slicer.mrmlScene.Clear(0)
wait(500)
after_close = len(g.scene.all_node_items())
print(f"  canvas nodes after Close Scene: {after_close}")
check(len(volumes()) == 0, "scene is empty after close")
slicer.util.loadScene(mrb_path)
wait(800)
names = sorted(ni.node_data.NODE_NAME for ni in g.scene.all_node_items())
check(names == ['Crop Volume', 'Markups', 'New Markup', 'Sample Data'],
      f"graph restored from the .mrb ({names})")
check(len(g.scene._edges) == 3, "edges restored")
check(len(volumes()) == 0, "no computed volumes were loaded from the file")
g.select(g.by_name('Crop Volume'))
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
check(array(g.out(g.by_name('Crop Volume'), 'volume_out')).shape == smaller,
      "the restored graph gives the same crop")
check(len(slicer.util.getNodesByClass('vtkMRMLScriptedModuleNode')) >= 1,
      "graph carrier node present")
carriers = [n for n in slicer.util.getNodesByClass('vtkMRMLScriptedModuleNode')
            if n.GetAttribute('NodeEditorGraph') == '1']
check(len(carriers) == 1, f"exactly one graph carrier ({len(carriers)})")

g.finish()
