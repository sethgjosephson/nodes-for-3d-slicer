# Roadmap

## Done

### Engine
- [x] QGraphicsScene canvas in a bottom dock widget
- [x] PythonQt compatibility shim (`NodeGraph/_qt.py`)
- [x] Typed ports with per-type colors and connection validation
- [x] Incremental execution: only dirty ancestors of the target re-run
- [x] Failed nodes block their descendants and show an error badge
- [x] Async nodes block their descendants until the CLI finishes
- [x] Upstream MRML edits from any source mark downstream nodes dirty
- [x] Property changes re-run the active viewer slot (opt-out per node via `AUTO_EXECUTE`)
- [x] Disabled nodes pass their input through
- [x] Input changes are detected from the data, not from any modified event
- [x] Edits made outside the graph re-run the viewed chain
- [x] Automatic re-runs keep the view's zoom, pan and layout

### Scene integration
- [x] Graph-created MRML nodes are not saved with the scene and are grouped under a "Node Editor (auto)" folder
- [x] Closing the scene marks every node dirty without clearing the graph
- [x] Graph is stored in the scene and restored when an `.mrb` is loaded
- [x] Graph files carry a format version and stable node type ids
- [x] Segment Editor and Markups nodes warn when their input changes under hand-edited data
- [x] Deleting a node removes the data it created
- [x] Hand-placed markups and the crop ROI are saved in the graph

### Editing
- [x] Tab search with category headers
- [x] Copy, cut, paste, undo, redo
- [x] Undo and redo keep computed data for unchanged nodes
- [x] Auto-connect on add and paste
- [x] Drop a node on an edge to insert it
- [x] Shake a node to disconnect it
- [x] Deleting a node between two nodes splices the edge
- [x] Ten viewer slots (keys 1..9, 0)
- [x] F key shows the selected output in a single view
- [x] Demo graph and "Default on Launch" toolbar buttons

### Nodes
- [x] Sample Data, Load Volume, Save Volume
- [x] Threshold (keep values or binary mask), Gaussian Smooth, Median Filter
- [x] Simple Filter (14 SimpleITK filters)
- [x] Crop Volume (own ROI or a connected ROI markup)
- [x] Volume Math, Resample Volume
- [x] New Markup, Save Data
- [x] Segment Filter, Mask Volume, Label Map to Segmentation
- [x] Surface Model, Segment Statistics
- [x] Segmentation, Segment Editor, Segmentations
- [x] Registration (BRAINSFit, async), Apply Transform, Transforms
- [x] Volume Rendering, Models, Volumes, Markups
- [x] Layout

### Testing
- [x] Self-tests for scene, nodes, edges, execution, failure isolation, Simple Filter, volume rendering display node, and serialization
- [x] `SLICER_NODE_EDITOR_DEBUG=1` logging switch
- [x] Workflow tests that drive the canvas inside Slicer (`tests/`)

## Planned

### Engine
- [ ] Cache eviction for long chains on large volumes
- [ ] Offer to transform hand-edited segmentations and markups when their input moves

### Editing
- [ ] Backdrop boxes
- [ ] Minimap
- [ ] Undo for node moves and property changes
- [ ] Drag a volume from the Data module onto the canvas

### Nodes
- [ ] Grow from Seeds
- [ ] Apply Transform for segmentations, models and markups
- [ ] Line Profile
- [ ] DICOM loader
- [ ] Python script
- [ ] Generic CLI module
- [ ] Batch process over a folder
- [ ] Sequences (4D)
- [ ] Slice foreground and label layer routing
- [ ] Slice viewer (per-slice control)

### Distribution
- [ ] Extensions Index submission
- [ ] CI running Slicer self-tests
- [ ] Notebook export
- [ ] Documentation site
- [ ] Demo video
