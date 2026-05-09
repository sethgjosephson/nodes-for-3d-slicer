# Roadmap: Nodes for 3D Slicer

A Nuke-style node graph extension for 3D Slicer.

## Phase 1 — Foundation ✅
Core graph infrastructure working inside Slicer.

- [x] Project scaffold and CMakeLists extension structure
- [x] Custom QGraphicsScene engine (NodeGraphQt rejected for stability)
- [x] PythonQt compatibility shim (`NodeGraph/_qt.py`) — works in Slicer's Python 3.12 build
- [x] Canvas embedded as a persistent **bottom dock widget** (visible across all modules)
- [x] Load Volume node — loads a file via `slicer.util.loadVolume`
- [x] Sample Data node — picks from Slicer's built-in samples (MRHead, prostate, etc.)
- [x] Threshold node — SimpleITK binary threshold
- [x] Save Volume node
- [x] Executor walks a 3-node graph (Sample Data → Threshold → Save) successfully
- [x] Graph saves/loads to JSON (Save Graph / Load Graph buttons)
- [x] Multi-file sample sets clean up ALL their MRML nodes when switched

## Phase 2 — Node Library Expansion
Wrap the most-used Slicer tools as nodes.

- [x] Gaussian Smooth, Median Filter
- [ ] Edge Detection filter
- [ ] Label Map → Segmentation conversion
- [ ] Grow from Seeds segmentation node
- [x] Volume Rendering node (uses Slicer's native VR module via `LINKED_MODULE`)
- [x] Layout node (4-up routing)
- [x] BrainsFit registration scaffolding
- [x] Apply Transform scaffolding
- [ ] Crop Volume node
- [ ] Surface model generation (Marching Cubes)
- [ ] Slice viewer node (per-slice control)

## Phase 3 — UX Polish ✅ (mostly)
Make it feel like Nuke.

- [x] Typed port colors (volume / segmentation / transform / model / labelmap / any)
- [x] Port type validation in connection logic (output→input only, type-compat splice)
- [x] Properties panel — auto-built from each node's PROPERTIES list
- [x] Per-node `LINKED_MODULE` hook — opens Slicer's native module widget for that node
- [x] Tab search popup with category headers and keyboard navigation
- [x] **Single-click selects, double-click loads settings** (so dragging never wipes panel context)
- [x] **Undo / Redo** (Ctrl+Z, Ctrl+Y) — snapshot-based, captures structural changes
- [x] **Copy / Cut / Paste** (Ctrl+C, Ctrl+X, Ctrl+V) — preserves selected subgraph and internal edges
- [x] **Auto-connect on Tab-add** (selected node → new node, splices into existing pipe)
- [x] **Auto-connect on Paste** (selected node → entry of pasted graph)
- [x] **Drag-and-drop into pipe** (orange highlight while hovering, splices on drop)
- [x] **Shake-to-disconnect** (rapidly wiggling a node disconnects it; middle-of-pipe nodes splice OUT cleanly)
- [x] **Multi-slot viewer routing** — keys 1-9 and 0 (10 slots), each with a unique badge color
- [x] Visibility scoping — viewing one volume hides previous volume renderings
- [ ] Node groups / backdrop boxes for annotation
- [ ] Minimap for large graphs
- [ ] Move + property changes captured for undo

## Phase 4 — Scene Integration
Tie the graph to Slicer's MRML scene lifecycle.

- [x] Dirty node highlighting (orange dot)
- [x] Incremental execution (only re-runs dirty ancestors of the target)
- [ ] Graph state serializes into `vtkMRMLScriptedModuleNode` so it travels with .mrb scene saves
- [ ] MRML scene observer: dropping a volume node onto the canvas auto-creates a Load node
- [ ] Bidirectional dirty: changes to MRML nodes outside the graph mark dependent graph nodes dirty

## Phase 5 — Advanced Nodes
Power-user and research features.

- [ ] Python Script node (inline code editor)
- [ ] CLI Module node (generic wrapper for any installed Slicer CLI)
- [ ] Batch process node (iterate over a folder of volumes)
- [ ] Jupyter notebook export (graph → runnable .ipynb)
- [ ] DICOM import node

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
| `Double-click` | Load this node's settings in left panel |
| `Ctrl+C` / `X` / `V` | Copy / Cut / Paste |
| `Ctrl+Z` / `Y` | Undo / Redo |
| `Del` / `Backspace` | Delete selected nodes |
| `F` | Frame all (or selected) nodes |
| `Esc` | Deselect |
| Scroll | Zoom |
| Middle-drag | Pan |
| Drag-and-shake | Disconnect node from its edges |
