# Architecture: Nodes for 3D Slicer

## Overview

A 3D Slicer scripted-module extension that replaces the traditional panel-based
workflow with a procedural node graph in the style of visual-effects compositing
software. Users drag nodes onto a canvas, wire them together, and execute the
graph — Slicer's underlying CLI modules and Python API do the actual work,
completely unchanged.

---

## Stack Constraints

| Layer | Version |
|---|---|
| 3D Slicer | 5.x |
| Python | 3.9 (bundled) |
| Qt | 5.15.2 (bundled) |
| Python Qt binding | PySide2 5.15 (bundled) |
| Node graph library | NodeGraphQt (PySide2-native) |

**Critical:** Do NOT install a different Qt or PySide2. Everything must use
Slicer's bundled copies.

---

## Component Map

```
SlicerNodeEditor.py          Slicer module entry point
│
├── NodeGraph/
│   ├── canvas.py            NodeGraphQt graph + context menus
│   ├── node.py              SlicerBaseNode (all nodes inherit this)
│   ├── port.py              Port type constants (VOLUME, SEGMENTATION, …)
│   ├── edge.py              (future) custom edge rendering / validation
│   └── executor.py          Topological sort + execute() dispatch
│
└── Nodes/
    ├── io_nodes.py          Load Volume, Save Volume
    ├── filter_nodes.py      Threshold, Gaussian Smooth, (more)
    ├── segment_nodes.py     Segmentation
    ├── register_nodes.py    Registration (BrainsFit)
    └── viz_nodes.py         Volume Rendering
```

---

## Data Flow

```
[Load Volume] ──volume──► [Threshold] ──volume──► [Gaussian Smooth] ──volume──► [Volume Rendering]
                                                         │
                                                         └──volume──► [Save Volume]
```

- Each port carries a **vtkMRMLNode reference** (by object, passed in-memory).
- The executor resolves the DAG topologically, calls `node.execute(inputs)`,
  and forwards its output dict to connected downstream nodes.
- Nodes read parameters from NodeGraphQt's built-in property widgets
  (text inputs, float sliders, combo menus).

---

## Node Authoring Pattern

```python
class MyFilterNode(SlicerBaseNode):
    __identifier__ = "slicer.filters"   # must be unique per category
    NODE_NAME = "My Filter"
    NODE_COLOR = (100, 130, 80)

    INPUT_PORTS  = [("volume_in",  "Volume")]
    OUTPUT_PORTS = [("volume_out", "Volume")]

    def __init__(self):
        super().__init__()
        self.add_float_input("strength", "Strength", value=1.0)

    def execute(self, inputs):
        node = inputs["volume_in"]
        # ... call slicer.cli.run() or SimpleITK here ...
        return {"volume_out": output_node}
```

Register the new class in `canvas.py:_ALL_NODE_TYPES` and it appears in the
right-click context menu automatically.

---

## Serialization

NodeGraphQt serializes the graph to JSON natively (`graph.save_session(path)`).
The JSON stores node types, positions, property values, and connections.
Graphs can be reloaded with `graph.load_session(path)` — the executor re-runs
them from scratch (non-destructive / procedural).

Future: embed graph JSON in a `vtkMRMLScriptedModuleNode` so it travels with
the Slicer `.mrb` scene file.

---

## Milestones

See `ROADMAP.md` for the full phased plan.
