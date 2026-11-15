# Nodes for 3D Slicer

A node-graph editor for [3D Slicer](https://slicer.org). Each node wraps a Slicer operation. Edges carry MRML data (volumes, segmentations, transforms, markups, models) between nodes.

Status: working prototype. Requires 3D Slicer 5.10.

## Install

1. Clone this repository.
2. In Slicer, open **Edit > Application Settings > Modules > Additional module paths**.
3. Add the `SlicerNodeEditor/` folder from the clone.
4. Restart Slicer.
5. Open **Utilities > Node Editor**. The canvas docks at the bottom of the main window.

## Quick start

1. Hover the canvas and press `Tab`.
2. Type "sample" and pick **Sample Data**.
3. Choose MRHead in the node's dropdown and press `1`.
4. Press `Tab` and add **Volume Rendering**. It connects to the selected node.
5. Press `1` with Volume Rendering selected.

## Nodes

| Node | Category | Description |
|---|---|---|
| Sample Data | I/O | Loads a Slicer sample volume. |
| Load Volume | I/O | Loads a volume from a file path. |
| Save Volume | I/O | Writes the input volume to a file path. |
| Save Data | I/O | Writes any input to a file path. The extension sets the format. |
| New Markup | I/O | Creates a point list, line, curve, plane or ROI to place in the views. |
| Volumes | I/O | Opens the Volumes module on the input volume. |
| Markups | I/O | Opens the Markups module on the input markup. |
| Threshold | Filters | Keeps or masks voxels inside an intensity range. |
| Gaussian Smooth | Filters | Smooths the input volume with a Gaussian kernel. |
| Median Filter | Filters | Applies a median filter to the input volume. |
| Simple Filter | Filters | Applies one of 14 SimpleITK filters, chosen from a dropdown. |
| Volume Math | Filters | Combines two volumes voxel by voxel. |
| Crop Volume | Filters | Crops the input volume to its own ROI or to a connected ROI markup. |
| Segmentation | Segmentation | Creates a segmentation from the input volume by threshold or Otsu. |
| Segment Editor | Segmentation | Opens the Segment Editor on the input volume and segmentation. |
| Segmentations | Segmentation | Opens the Segmentations module on the input segmentation. |
| Segment Filter | Segmentation | Applies one of 8 clean-up operations to every segment. |
| Mask Volume | Segmentation | Keeps the voxels of a volume that lie inside a segmentation. |
| Label Map to Segmentation | Segmentation | Creates one segment per label value of the input volume. |
| Surface Model | Segmentation | Builds a surface model from a segmentation. |
| Segment Statistics | Measure | Computes per-segment statistics into a table. |
| Registration | Registration | Registers a moving volume to a fixed volume with BRAINSFit. |
| Apply Transform | Registration | Applies a transform to a copy of the input volume. |
| Resample Volume | Registration | Resamples a volume onto a reference grid, optionally through a transform. |
| Transforms | Registration | Opens the Transforms module on the input transform. |
| Volume Rendering | Visualization | Renders the input volume in the 3D view. |
| Models | Visualization | Opens the Models module on the input model. |
| Layout | Layout | Routes up to four inputs to Slicer's views. |

### Simple Filter

| Group | Filters |
|---|---|
| Edges | Gradient Magnitude, Sobel, Canny |
| Denoising | Curvature Flow, Anisotropic Diffusion |
| Morphology | Opening, Closing, Fill Hole, Grind Peak |
| Intensity | Invert, Rescale, Sigmoid, Laplacian Sharpening |
| Bias correction | N4 |

### Segment Filter

| Group | Operations |
|---|---|
| Islands | Keep Largest Island, Remove Small Islands |
| Smoothing | Median, Closing, Opening |
| Margin | Grow, Shrink |
| Holes | Fill Holes |

### Volume Math

`A - B`, `A + B`, `A x B`, `|A - B|`, Minimum, Maximum, Mean. Both inputs must be on the same grid.

## Keys

| Key | Action |
|---|---|
| `Tab` | Open the node search at the cursor. |
| `1`..`9`, `0` | Assign the selected node to viewer slot 1..10 and display it. |
| `F` | Show the selected node's output in a single view. With nothing selected, frame all nodes. |
| `D` | Disable or enable the selected nodes. A disabled node passes its input through. |
| `Del`, `Backspace` | Delete the selected nodes. A node between two nodes is spliced out. |
| `Ctrl+C`, `Ctrl+X`, `Ctrl+V` | Copy, cut, paste. |
| `Ctrl+Z`, `Ctrl+Y` | Undo, redo. |
| `Esc` | Deselect. |
| Double-click | Show the node's settings in the left panel. |
| Scroll | Zoom. |
| Middle-drag | Pan. |
| Shake while dragging | Disconnect the node. |
| Drop on an edge | Insert the node into the edge. |

## Node badges

| Badge | Meaning |
|---|---|
| Orange dot | Needs to re-run. |
| Blue dot | Running. |
| Red `!` | Last run failed. |
| Amber `!` | Input changed under hand-edited data. |
| Numbered circle | Assigned viewer slot. |

## Saving

**Save Graph** and **Load Graph** write and read the graph as JSON. The graph is also stored in the scene, so it saves and loads with `.mrb` files. Nodes created by the graph are not saved with the scene; they are grouped under a "Node Editor (auto)" folder in the Data module.

Hand-placed markups and the Crop Volume ROI are saved in the graph. Deleting a node removes the data it created from the scene.

## Layout

| Path | Contents |
|---|---|
| `SlicerNodeEditor/SlicerNodeEditor.py` | Module entry point, toolbar, properties panel, self-tests. |
| `SlicerNodeEditor/NodeGraph/` | Canvas, scene, executor, viewer routing. |
| `SlicerNodeEditor/Nodes/` | Node classes. |
| `docs/design/` | Design notes. |
| `tests/` | Workflow tests that run inside Slicer. |

## Adding a node

Subclass `SlicerBaseNode` and implement `execute(inputs)`, which returns `{port_name: mrml_node}`. To wrap a Slicer module instead, subclass `LinkedModuleNode` and set `LINKED_MODULE` and `INPUT_SETTERS`. Register the class in `Nodes/__init__.py`.

## Debugging

Set `SLICER_NODE_EDITOR_DEBUG=1` before starting Slicer to log setter and observer failures. Self-tests run from **Reload & Test** on the Node Editor module (developer mode).

## Tests

| Command | Runs |
|---|---|
| `bash tests/run.sh tests/workflows/NAME.py` | One workflow test in its own Slicer session. |
| `bash tests/run_all.sh` | Every workflow test, with a pass and fail summary. |

Logs and screenshots are written to `tests/out/NAME/`. The tests download Slicer sample data on first use. Set `SLICER` to the path of `Slicer.exe` to use a different install.

## License

[MIT](LICENSE)
