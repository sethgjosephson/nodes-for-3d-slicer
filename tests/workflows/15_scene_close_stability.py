# Closing the scene, clearing it from another module's test set-up and
# reloading the demo, repeated: the sequence that once ended a session
# without a traceback.
g = G(editor)


def cycle(i):
    section(f"cycle {i}: demo, view, close scene")
    editor._on_load_demo()
    wait(300)
    vr = g.by_name("Volume Rendering", 1)
    g.select(vr)
    g.press('1')
    vols = g.by_name("Volumes")
    g.select(vols)
    g.press('2')
    check(not g.errors(), f"no errors ({g.errors()})")
    # An edit that leaves a debounced callback pending when the scene goes.
    thresh = g.by_name("Threshold")
    out = g.out(thresh, 'volume_out')
    arr = slicer.util.arrayFromVolume(g.out(g.by_name("Sample Data", 2),
                                            'volume_out'))
    arr[0, 0, 0] += 1
    slicer.util.arrayFromVolumeModified(
        g.out(g.by_name("Sample Data", 2), 'volume_out'))
    g.set(thresh, 'lower', 60.0 + i)
    slicer.mrmlScene.Clear(0)
    wait(900)
    check(len(g.scene.all_node_items()) == 0,
          "Close Scene leaves an empty canvas")
    check(len(slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode')) == 0,
          "no volumes left")


for i in range(3):
    cycle(i)

section("another module's test clears the scene under a loaded graph")
editor._on_load_demo()
wait(300)
g.select(g.by_name("Volumes"))
g.press('1')
slicer.util.selectModule('SegmentEditor')
wait(300)
slicer.mrmlScene.Clear()          # what a module test's setUp does
wait(900)
slicer.util.selectModule('SlicerNodeEditor')
wait(300)
editor._on_load_demo()
wait(300)
g.select(g.by_name("Volume Rendering", 0))
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
check(not g.by_name("Volume Rendering", 0).node_data.is_dirty,
      "the demo runs again after the scene was cleared from elsewhere")

section("module reload")
slicer.util.reloadScriptedModule('SlicerNodeEditor')
wait(800)
new_editor = slicer.modules.SlicerNodeEditorWidget
check(new_editor is not editor, "a new module widget after reload")
g2 = G(new_editor)
new_editor._on_load_demo()
wait(300)
g2.select(g2.by_name("Volumes"))
g2.press('1')
check(not g2.errors(), f"no errors after reload ({g2.errors()})")
# The old dock is removed from the window and deleted when control returns
# to Qt's event loop, which does not happen inside this script; count the
# docks that are still shown.
docks = [d for d in slicer.util.mainWindow().findChildren('QDockWidget')
         if d.objectName == 'NodeEditorDock' and d.visible]
check(len(docks) == 1, f"one canvas dock shown after reload ({len(docks)})")

g.finish()
