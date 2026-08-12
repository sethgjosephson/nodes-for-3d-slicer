# Roadmap: Nodes for 3D Slicer

A procedural node-graph extension for 3D Slicer, modeled on visual-effects compositing software.

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
- [x] **Generic SimpleFilterNode** — one node, a curated set of 14 single-input SimpleITK filters (edge detection, denoising, morphology, intensity, N4 bias correction). Filter dropdown with a per-filter parameter form; slow filters opt out of the live auto-rerun loop. Adding a filter is one `FILTERS` entry in `simple_filter_node.py`.
- [x] Edge Detection filter (Sobel / Canny / Gradient Magnitude, via SimpleFilterNode)
- [ ] Label Map → Segmentation conversion
- [ ] Grow from Seeds segmentation node
- [ ] Surface Model node (Marching Cubes → `vtkMRMLModelNode`)
- [ ] Segment Statistics node (segmentation + volume → table)
- [ ] Line Profile node (volume + line markup → table)
- [ ] DICOM Loader node (study UID → loaded volume)
- [ ] Slice viewer node (per-slice control)

## Phase 3 — UX Polish ✅ (mostly)
Make it feel like a procedural compositor.

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
- [x] **D key**: disable / enable selected nodes (compositor-style passthrough)
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
- [x] **Graph state in `vtkMRMLScriptedModuleNode`** so the graph travels inside `.mrb` saves (tagged carrier node, restore on EndImportEvent, duplicate-carrier consolidation; the graph file remains the canonical artifact).
- [ ] Drop volume on canvas auto-Load (covered above under Phase 3).

## Phase 4.5 — Hardening (from the August 2026 feasibility review)
Correctness and robustness fixes before widening the node library. See
[`docs/design/feasibility_review_2026-08.md`](docs/design/feasibility_review_2026-08.md)
for the full analysis.

- [x] **Executor failure isolation** — a node that raises now shows a red error badge and blocks all of its descendants for that pass, instead of letting them run against stale or missing inputs and be marked clean.
- [x] **Async execution barrier** — an async node (Registration) left mid-flight no longer lets downstream nodes cook against its empty placeholder outputs. Descendants stay blocked; the CLI completion callback marks the node clean, dirties downstream, and re-cooks the active viewer slot automatically.
- [x] **False re-dirty fix** — during a pipeline pass, upstream writes fired observers bound on the previous run, re-marking freshly-cleaned chains dirty ~100 ms after every cook. Graph-internal writes are now recognised and skipped; external edits are still detected.
- [x] **Apply Transform no longer mutates its input** — it copies the volume into an output it owns and transforms the copy, so other branches off the same source stay untouched and harden mode is no longer destructive to shared data.
- [x] **Graph file format versioning** — saved graphs carry a `version` field and a stable per-node `type` id resolved through `Nodes.NODE_TYPE_REGISTRY`, decoupled from Python class names. Legacy files still load; files from a newer format refuse to load with a clear message.
- [x] **Stale-input warning on edit-state nodes** — Segment Editor and Markups nodes show an amber badge when an upstream input changes under hand-edited content (which cannot be re-cooked and may be misaligned). Double-clicking the node acknowledges the warning.
- [x] **Debug logging switch** — `SLICER_NODE_EDITOR_DEBUG=1` logs swallowed setter misses and observer failures, for smoke-checking after Slicer upgrades.
- [x] **Self-test coverage** — module self-tests now cover pipeline execution on a synthetic volume, executor failure isolation, and a serialisation round trip (plus the original scene/node/edge tests).
- [x] **Threshold mode property** — "Keep values" (default; original intensities inside the range, renders like anatomy in 3D) vs "Binary mask" (0/1 output for mask-style downstream steps). A 0/1 mask is nearly invisible in volume rendering, which was the old default's surprise.
- [x] **Volume Rendering transfer-function rescue** — presets stay in charge; the window/level sync only fires when the current transfer function provably renders the data invisibly (zero sampled opacity across the volume's scalar range, e.g. a 0/1 mask under an anatomical preset). A hand-tweaked VR property (detected via MTime) is edit-state and never touched. (First version synced unconditionally, which replaced every preset with a grayscale ramp; fixed same day.)
- [x] **Volume Rendering owns ONE display node** — previously the VR node looked display state up by volume identity, so a D-key passthrough (which swaps a different upstream volume into the node) minted a fresh display node with a default fitted ROI, appearing to randomly reset the user's cropping ROI. The graph node now owns a single display node and re-attaches it to whatever volume flows in; ROI and transfer function ride along.
- [ ] **Cache eviction policy** — intermediates are full volume copies; deep chains on large CTs will need "keep cooked outputs only for viewer-routed nodes, recompute interior nodes on demand" (interacts with input observers).
- [ ] **Forward-fix for stale edit-state data** — when the upstream change is a known transform, offer to resample or transform the hand-edited segmentation/markups forward instead of only warning.

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
| `D` | Disable / enable selected nodes (compositor-style passthrough) |
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

The node graph IS the project file, like a procedural compositor's
project script. The MRML
scene is the cooked output cache, regeneratable from the graph. See
[`docs/design/procedural_workflow_analysis.md`](docs/design/procedural_workflow_analysis.md)
for the long-form analysis of how every documented Slicer module maps
onto a procedural-fitness scale, the 13 edge cases to pre-plan for, and
the architectural strategies for each friction category.
