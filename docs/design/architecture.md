# Architecture

A 3D Slicer scripted module. Nodes on a canvas wrap Slicer operations; the executor runs them in dependency order and passes MRML nodes along edges.

## Stack

| Layer | Version |
|---|---|
| 3D Slicer | 5.10 |
| Python | 3.12 (bundled) |
| Qt binding | PythonQt (`import qt`) |
| Image processing | SimpleITK, Slicer CLI modules |

## Components

```
SlicerNodeEditor.py      module entry point, toolbar, properties panel, self-tests
NodeGraph/
  _qt.py                 PythonQt shim
  canvas.py              QGraphicsView: pan, zoom, keys, clipboard
  scene.py               QGraphicsScene: nodes, edges, undo, serialization
  node_item.py           node drawing and badges
  port_item.py           port drawing
  edge_item.py           edge drawing
  search_popup.py        Tab search
  executor.py            topological execution with dirty tracking
  viewer_router.py       viewer slots 1..10
Nodes/
  base_node.py           SlicerBaseNode, LinkedModuleNode, port types
  io_nodes.py            Sample Data, Load / Save Volume, Volumes, Markups
  filter_nodes.py        Threshold, Gaussian Smooth, Median Filter
  simple_filter_node.py  Simple Filter
  process_nodes.py       Crop Volume
  segment_nodes.py       Segmentation, Segment Editor, Segmentations
  register_nodes.py      Registration, Apply Transform, Transforms
  viz_nodes.py           Volume Rendering, Models
  layout_node.py         Layout
  __init__.py            node registry
```

## Execution

- Each port carries an MRML node reference in memory.
- Pressing a slot key runs the dirty ancestors of the selected node, then the node, then routes its output to the views.
- A node keeps the MRML nodes it creates in `_owned_outputs` and reuses them on later runs.
- A failed or still-running node blocks its descendants for that run.
- Each node observes its input MRML nodes and marks itself and its descendants dirty when they change.

## Node definition

| Attribute | Purpose |
|---|---|
| `NODE_NAME`, `CATEGORY` | Name and search category. |
| `INPUT_PORTS`, `OUTPUT_PORTS` | `(name, label, type)` tuples. |
| `PROPERTIES` | Parameters; the properties panel is built from these. |
| `execute(inputs)` | Returns `{port_name: mrml_node}`. |
| `route_to_viewer()` | Shows the output for a slot key. |
| `AUTO_EXECUTE` | False keeps the node out of re-runs triggered by property changes. |
| `EDIT_STATE` | True for nodes holding hand-edited data. |
| `LINKED_MODULE`, `INPUT_SETTERS` | `LinkedModuleNode` only: module to open and the widget setters for each input. |
| `NODE_TYPE` | Type id written to graph files; defaults to the class name. |

## Serialization

`scene.serialise()` returns a dict with a format `version`, nodes (type, position, properties, slot, disabled), and edges. The module writes it to JSON files and to a `vtkMRMLScriptedModuleNode` in the scene so it saves with `.mrb` files.
