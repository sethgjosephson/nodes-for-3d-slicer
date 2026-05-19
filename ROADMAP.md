# Roadmap: Nodes for 3D Slicer

A Nuke-style node graph extension for 3D Slicer.

## Phase 1 — Foundation ✅
Core graph infrastructure working inside Slicer.

- [x] Project scaffold and CMakeLists extension structure
- [x] Custom QGraphicsScene engine (NodeGraphQt rejected for stability)
- [x] PythonQt compatibility shim (`NodeGraph/_qt.py`)
- [x] Canvas as a persistent bottom dock widget (visible across all modules)
- [x] Load Volume, Save Volume, Sample Data, Threshold, Save → Threshold pipeline running end-to-end
- [x] Multi-file sample sets clean up all their MRML nodes when switched
- [x] Graph saves/loads to JSON (Save Graph / Load Graph buttons)

## Phase 2 — Node Library Expansion
Wrap the most-used Slicer tools as nodes.

- [x] Gaussian Smooth, Median Filter
- [x] Volume Rendering node (uses Slicer's native VR module via `LINKED_MODULE`)
- [x] Layout node (4-up routing)
- [x] BrainsFit registration (now async + cancel-on-rerun)
- [x] Apply Transform
- [x] Crop Volume node (`process_nodes.py`)
- [x] Volumes / Models / Markups / Transforms / Segmentations / Segment Editor as linked-module nodes
- [ ] **Generic SimpleFilterNode** — single node driven by SimpleITK's filter list (replaces ~18 hand-written CLI wrappers)
- [ ] Edge Detection filter
- [ ] Label Map → Segmentation conversion
- [ ] Grow from Seeds segmentation node
- [ ] Surface Model node (Marching Cubes → `vtkMRMLModelNode`)
- [ ] Segment Statistics node (segmentation + volume → table)
- [ ] Line Profile node (volume + line markup → table)
- [ ] DICOM Loader node (study UID → loaded volume)
- [ ] Slice viewer node (per-slice control)

## Phase 3 — UX Polish ✅ (mostly)
Make it feel like Nuke.

- [x] Typed port colors (volume / labelmap / segmentation / transform / model / markup / table / plot / text / color / any / sequence reserved)
- [x] Port type validation in connection logic (output→input only, type-compat splice)
- [x] Properties panel — auto-built from each node's PROPERTIES list
- [x] Per-node `LINKED_MODULE` hook — opens Slicer's native module widget for that node
- [x] Tab search popup with category headers and keyboard navigation
- [x] Single-click selects, double-click loads settings (so dragging never wipes panel context)
- [x] Undo / Redo (Ctrl+Z, Ctrl+Y) — snapshot-based for structural changes
- [x] Copy / Cut / Paste (Ctrl+C, Ctrl+X, Ctrl+V) — preserves selected subgraph and internal edges, including `is_disabled` state
- [x] Auto-connect on Tab-add and on Paste
- [x] Drag-and-drop into pipe (orange highlight while hovering, splices on drop)
- [x] Shake-to-disconnect (middle-of-pipe nodes splice OUT cleanly)
- [x] Delete-with-splice — deleting a middle-of-pipe node reconnects upstream → downstream
- [x] Multi-slot viewer routing — keys 1-9 and 0 (10 slots), each with a unique badge color
- [x] **D key**: disable / enable selected nodes (Nuke-style passthrough)
- [x] **F key**: fullscreen the selected node's output (3D-only for VR, single slice for volumes); frames canvas when nothing selected
- [x] Visibility scoping — viewing one volume hides volume renderings of OTHER volumes only
- [x] VR / Models routing keeps slice context (Conventional layout, not pure 3D)
- [x] Demo toolbar button + bundled `Resources/demo_workflow.json`
- [x] "Default on Launch" toolbar toggle (writes `Modules/HomeModule`)
- [ ] Node groups / backdrop boxes for annotation
- [ ] Minimap for large graphs
- [ ] Capture undo for node moves and property changes (debounced)
- [ ] Drag-drop a volume from the Data module onto the canvas to auto-create a Load / Sample Data node already pointing at it

## Phase 4 — Scene Integration & Procedural Mechanics ✅ (mostly)
Tie the graph to Slicer's MRML scene lifecycle.

- [x] Dirty node highlighting (orange dot)
- [x] Async-pending indicator (blue ellipsis dot) for long-running CLI nodes
- [x] Incremental execution (only re-runs dirty ancestors of the target)
- [x] **MRML hygiene** — every graph-created MRML node has `SetSaveWithScene(False)` and is parented under a `Node Editor (auto)` Subject Hierarchy folder. `.mrb` saves no longer accumulate stale intermediates.
- [x] **Scene-close survival** — `vtkMRMLScene.StartCloseEvent` observer drops cached MRML pointers and marks every node dirty WITHOUT destroying the graph. The graph is treated as a recipe; the MRML scene is the cooked output cache. Reopening any `.mrb` keeps the graph alive; press 1 re-cooks.
- [x] **Bidirectional dirty propagation** — MRML `ModifiedEvent` observers on each node's resolved input MRML nodes. Edits made anywhere (in another module, by a script, by the user clicking) auto-mark dependent graph nodes dirty. Debounced 100 ms.
- [x] `_self_modified` reentrance flag so a node's own writes during `execute()` don't bounce back through its observers as a false dirty mark.
- [x] **Live auto-rerun on property change** — debounced 300 ms, walks the chain feeding the active viewer slot, opts cheap nodes in via `AUTO_EXECUTE` class attribute (defaults True; off on Registration, LoadVolume, Segmentation, SegmentEditor).
- [x] Async CLI for RegistrationNode (BRAINSFit) — canvas stays responsive during multi-minute runs, with cancel-on-rerun.
- [x] `_owned_outputs` separated from `_cache` so disabled→enabled cycles never compound effects (was the double-smoothing bug).
- [ ] **Graph state in `vtkMRMLScriptedModuleNode`** so the graph travels inside `.mrb` saves (the graph file remains the canonical artifact; this is for scene+graph travelling together).
- [ ] Drop volume on canvas auto-Load (covered above under Phase 3).

## Phase 5 — Advanced Nodes
Power-user and research features.

- [ ] Python Script node (inline code editor)
- [ ] CLI Module node (generic wrapper for any installed Slicer CLI)
- [ ] Batch process node (iterate over a folder of volumes)
- [ ] Jupyter notebook export (graph → runnable .ipynb)
- [ ] Sequences (4D) support — `SEQUENCE` port type + `SequenceBrowserNode` emitting frame-change events for per-frame downstream invalidation
- [ ] Slice composite slot routing (background / foreground / label) as a per-route property

## Phase 6 — Distribution
Package and publish.

- [ ] Extension Manager submission (Extensions Index PR)
- [ ] CI: GitHub Actions running Slicer headless tests
- [ ] Documentation site
- [ ] Demo video / screencast

---

## Current keyboard shortcuts

| Key | Action |
|-----|--------|
| `Tab` | Open node search popup at cursor |
| `1`–`9`, `0` | Assign selected node to viewer slot 1–10 |
| `F` | Fullscreen the selected node's output (3D-only for VR/Models, single slice for volume outputs). Frames canvas if nothing selected. |
| `D` | Disable / enable selected nodes (Nuke-style passthrough) |
| `Double-click` | Load this node's settings in left panel |
| `Ctrl+C` / `X` / `V` | Copy / Cut / Paste (preserves disabled state, internal edges, subgraph) |
| `Ctrl+Z` / `Y` | Undo / Redo (structural changes; moves/props not yet captured) |
| `Del` / `Backspace` | Delete selected nodes (middle-of-pipe deletes splice the pipe back together) |
| `Esc` | Deselect |
| Scroll | Zoom |
| Middle-drag | Pan |
| Drag-and-shake | Disconnect node from its edges (splices out cleanly if middle-of-pipe) |
| Drag onto pipe | Insert node into the pipe (orange highlight previews) |

## Design philosophy

The node graph IS the project file, like a Nuke `.nk` script. The MRML
scene is the cooked output cache, regeneratable from the graph. See
[`docs/design/procedural_workflow_analysis.md`](docs/design/procedural_workflow_analysis.md)
for the long-form analysis of how every documented Slicer module maps
onto a procedural-fitness scale, the 13 edge cases to pre-plan for, and
the architectural strategies for each friction category.
