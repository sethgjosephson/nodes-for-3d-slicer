# Nodes for 3D Slicer

A Nuke-style **node graph editor** for [3D Slicer](https://slicer.org).
It replaces the traditional one-module-panel workflow with a procedural,
node-based pipeline where every Slicer tool is a draggable, connectable
node, and data flows through typed channels.

> Status: working prototype. The graph engine, all core editing
> shortcuts, and ~15 node types are functional in Slicer 5.10
> (Python 3.12 / PythonQt). Full procedural integration with MRML
> observers and ephemeral intermediate nodes is in progress. See the
> [procedural workflow analysis](docs/design/procedural_workflow_analysis.md)
> for the design and current gaps.

---

## Why

3D Slicer is the standard tool for medical image processing, but its UX
is built around one module at a time, modal Apply buttons, and growing
clutter in the Data module as each step leaves its output behind. For
multi-step workflows (load, register, resample, segment, render), that
loop becomes the bottleneck.

This extension keeps Slicer's MRML scene and all its modules, and exposes
them through a graph editor at the bottom of the main window. Each node
wraps a Slicer module; edges carry typed MRML data (volumes,
segmentations, transforms, markups, models). Selecting a node either
loads its native module's widget in the left panel (so you get the full
Slicer UI for that operation), or shows a quick-edit form for nodes
without a backing module. Pressing `1` through `0` routes a node's
output to one of 10 viewer slots, the same way Nuke routes through its
viewer slots.

---

## Status

| Area | What works |
|---|---|
| **Engine** | Custom PySide-compatible QGraphicsScene. Nuke-style pan/zoom, bezier pipes, type-checked port connections. |
| **Editing** | Tab search popup, copy / cut / paste / undo / redo, shake-to-disconnect with splice-out, drag-into-pipe with live highlight. |
| **Viewer routing** | 10 slots (`1` through `9`, plus `0`), per-slot badge color, visibility scoping (the volume you're viewing keeps its volume rendering; others hide). |
| **Node library (~15 nodes)** | Sample Data, Load/Save Volume, Volumes, Threshold, Gaussian Smooth, Median Filter, Crop Volume, Markups, Segmentation, Segment Editor, Segmentations, Registration, Apply Transform, Transforms, Volume Rendering, Models, Layout (4-up). |
| **Linked-module pattern** | Double-click any module-linked node and Slicer auto-switches to that module's native widget, pre-pointed at the node's input. |
| **Persistent dock** | Canvas lives in a bottom dock widget that stays visible while you switch modules. |
| **MRML hygiene** | (in progress) hiding intermediate output nodes from the Data module so the scene stays clean. |

What's not yet built (see the [roadmap](ROADMAP.md) for full detail):
4D sequence support, `.mrb`-native graph persistence, auto-recompute
when upstream MRML changes (currently you press `1` to re-evaluate),
and a generic SimpleFilter node to expose all 18 of Slicer's CLI
Filtering modules through one configurable node.

---

## Install

1. Clone this repo somewhere on disk.
2. Open 3D Slicer (tested with 5.10).
3. **Edit, Application Settings, Modules, Additional module paths.**
4. Add the path to the `SlicerNodeEditor/` subfolder inside the clone.
5. Restart Slicer.
6. The "Node Editor" module is now available under the **Utilities**
   category. Selecting it once docks the canvas at the bottom of the
   main window, where it stays for the rest of the session.

The extension does not require any extra Python packages. It talks to
Slicer's bundled PythonQt and SimpleITK only.

---

## Quick start

1. Switch to the Node Editor module once to dock the canvas.
2. Hover the canvas. Press `Tab`: the search popup appears.
3. Type "sample" and click **Sample Data**. The node is placed and
   selected; the left panel shows its dropdown.
4. Pick MRHead from the dropdown. Press `1`. Slicer downloads and
   loads MRHead into the slice views.
5. With Sample Data still selected, hit `Tab` again and add **Volume
   Rendering**. It auto-connects after the Sample Data node.
6. Double-click the Volume Rendering node. The left panel switches to
   Slicer's native Volume Rendering module, pre-configured for MRHead.
7. Press `1` with the Volume Rendering node selected. Slicer switches
   to the 3D view with the volume rendered. Pick a preset, tweak the
   shift slider, and you're back in normal Slicer.

---

## Keyboard reference

| Key | Action |
|---|---|
| `Tab` | Open node search popup at cursor |
| `1` through `9`, `0` | Assign selected node to viewer slot 1 through 10 |
| Double-click a node | Load its settings in the left panel |
| Single-click | Select / drag (does NOT change the panel) |
| `Ctrl+C` / `X` / `V` | Copy / cut / paste, preserves the selected subgraph including internal edges |
| `Ctrl+Z` / `Y` | Undo / redo |
| `Del` / `Backspace` | Delete selected nodes. Middle-of-pipe deletions splice the pipe back together. |
| `F` | Frame all (or selected) nodes |
| `D` | Disable / enable selected nodes (Nuke-style passthrough). Disabled nodes skip their work and forward their input straight to their output. |
| `Esc` | Deselect |
| Scroll wheel | Zoom |
| Middle-mouse drag | Pan |
| Shake a node while dragging | Disconnect it from its edges (splices out cleanly if middle-of-pipe). |
| Drag a fresh node onto an existing pipe | Inserts the node into the pipe (orange highlight previews the splice). |

---

## How it works

- **`SlicerNodeEditor/`** is the Slicer scripted module. Entry point
  (`SlicerNodeEditor.py`) creates the canvas dock and the properties
  panel.
- **`SlicerNodeEditor/NodeGraph/`** is the graph engine. Pure
  `QGraphicsScene`-based, no third-party dependencies. The
  `_qt.py` shim adapts to whichever Qt-Python binding Slicer's build
  exposes (PythonQt, PySide2, or PySide6).
- **`SlicerNodeEditor/Nodes/`** is the wrappers. Each file groups
  related nodes (`io_nodes.py`, `filter_nodes.py`,
  `segment_nodes.py`, `register_nodes.py`, `viz_nodes.py`,
  `process_nodes.py`, `layout_node.py`). All extend `SlicerBaseNode`
  or `LinkedModuleNode` from `base_node.py`.
- **`docs/design/procedural_workflow_analysis.md`** is the long-form
  design rationale comparing Nuke's evaluation model with Slicer's
  MRML/module architecture, mapping every documented Slicer module
  onto a procedural-fitness scale, and enumerating 13 edge cases to
  pre-plan for.

To add a node for module X: extend `LinkedModuleNode`, set
`LINKED_MODULE = "ModuleName"`, declare `INPUT_PORTS` and `OUTPUT_PORTS`,
and supply an `INPUT_SETTERS` dict mapping each input port to the
module widget's setter method (for example,
`'volume_in': 'setMRMLVolumeNode'`). The base class handles configuring
the module widget when the node is selected.

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the phase-by-phase breakdown, and the
[procedural workflow analysis](docs/design/procedural_workflow_analysis.md)
for the deeper architectural plan.

Headline near-term work:

1. **Hide intermediate output nodes** from the Data module so the
   scene stays clean as graphs run.
2. **MRML `ModifiedEvent` observers** on inputs so upstream changes
   from any source (other modules, hand-edits, scripts) auto-mark our
   downstream nodes dirty.
3. **Async CLI** for `RegistrationNode` (BRAINSFit) so the canvas
   stays responsive during multi-minute registrations.
4. **`.mrb`-native graph serialization** so saving a Slicer scene also
   saves the graph.
5. **Generic `SimpleFilterNode`** exposing all ~18 of Slicer's CLI
   filtering modules through one configurable node.

---

## Compatibility

- 3D Slicer **5.10** (the version this was developed against).
- Python **3.12** (Slicer's bundled interpreter).
- Qt binding: **PythonQt**. PySide2 and PySide6 also supported via the
  shim if Slicer's build exposes either.

Earlier Slicer 5.x releases that ship PySide2 should work. The
extension auto-detects the Qt binding at import time.

---

## License

[MIT](LICENSE).
