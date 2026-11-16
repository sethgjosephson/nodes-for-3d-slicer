# extensions: SlicerDMRI Every graph in examples/ loads and runs to the end.
import glob
import os

g = G(editor)
examples = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'examples')
paths = sorted(glob.glob(os.path.join(examples, '*.json')))
check(len(paths) >= 3, f"example graphs found ({len(paths)})")

for path in paths:
    section(os.path.basename(path))
    g.load(path)
    n = len(g.scene.all_node_items())
    check(n > 0, f"loaded {n} nodes, {len(g.scene._edges)} edges")
    # A hand-placed ROI comes back from the file already placed.
    editor._on_execute_all()
    g.wait_async(900)
    wait(1500)
    # Nodes below an asynchronous node run when it finishes; run the rest now that it has.
    editor._on_execute_all()
    g.wait_async(900)
    wait(800)
    check(not g.errors(), f"no errors ({g.errors()})")
    check(not g.dirty(), f"every node ran ({g.dirty()})")
    screenshot(os.path.splitext(os.path.basename(path))[0])
    editor._on_clear()
    wait(300)

g.finish()
