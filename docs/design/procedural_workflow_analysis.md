# Procedural Workflow in Slicer — Roadblocks and Levers

A deep-dive comparing the pull-based evaluation model used by procedural
visual-effects compositors against Slicer's MRML/module architecture, with
concrete recommendations for our node graph.

## 1. The procedural VFX evaluation model in one paragraph

Every node in a procedural visual-effects compositor is a pure-ish
function from inputs (image+metadata streams) to outputs. Nodes are
nodes — there is no separate "scene." Evaluation is **lazy and
pull-based**: the viewer asks the active node for pixels at a given
frame; that node asks its inputs; the chain rolls upstream until a read
node or a cached value satisfies the request. A knob change marks the
touched node dirty and bumps a hash; any downstream pull recomputes.
Cached results are stored per-node, per-hash. Nothing is "created" in a
shared global state — every node owns its own output, ephemeral by
default. **The viewer is just a request; the graph is the canonical truth.**

## 2. Slicer's model in one paragraph

Slicer is built around a singleton **MRML scene** containing typed nodes
(`vtkMRMLScalarVolumeNode`, `vtkMRMLSegmentationNode`, etc.). Modules are
either CLI binaries (XML-described params, run as a subprocess), C++
loadable modules, or Python scripted modules. The Apply-button pattern
is dominant: the user wires up inputs in the module's GUI, presses
**Apply**, and the module mutates the scene by adding/modifying a new
node. Many operations are interactive (Segment Editor, Markups), where
the user's strokes/clicks commit directly into a MRML node. **The MRML
scene is the canonical truth; modules are imperative editors of it.**

The mismatch is structural: procedural compositing-graph nodes own their
output, Slicer modules edit shared scene state.

## 3. The three friction categories

### A. Apply-button modules

Most Slicer modules don't run until the user clicks Apply. CLI modules
in particular run in a subprocess and produce a fresh output node.

**Examples in our wrappers:**
- `RegistrationNode` (BRAINSFit) — multi-minute CLI invocation
- `CropVolumeNode` — fast logic call but still imperative
- Any Resample / Threshold / Smooth wrapped via SimpleFilters CLI
- Our own custom filter nodes already work around this by calling SITK
  directly inline.

**Why it bites us:** procedural pulls expect lazy evaluation. With CLI,
"pulling" a node means waiting tens of seconds for a subprocess.

### B. Stateful / interactive editing

Modules where the canonical operation is "user strokes/clicks shaped the
data, here's where it ended up." There is no parameter set that
reproduces the result.

**Examples:**
- **Segment Editor** — paint, erase, scissors, grow-from-seeds. The
  result is the segmentation; parameters of the *last* effect don't
  describe how the user got there.
- **Markups** — fiducials, lines, ROIs placed by clicks.
- **Volume Rendering presets** — once you tweak the opacity transfer
  function by hand, that handcrafted curve becomes the state.

**Why it bites us:** there is no "input → params → output" function to
re-execute. The node graph can _route_ this data through, but it cannot
*recompute* it from upstream changes.

### C. MRML scene pollution

Every operation produces a persistent named node in the scene, visible
in the Data module and saved into `.mrb` by default. Re-running an
operation either replaces the previous output (if the wrapper reuses
the cached MRML node) or creates a `_1` / `_2` clone.

**Why it bites us:** if a Threshold node in our graph is connected to a
Smooth, and the user tweaks Threshold's `lower` value 30 times, we end
up with either 30 stale volumes in the scene or — if we reuse — 30
intermediate states that overwrote each other with no history. Neither
is "procedural" in the visual-effects-compositor sense (each evaluation
lives in its own cache slot).

## 4. Primitives in Slicer we can lean on

Despite the mismatch, MRML actually exposes everything we need for a
substantially more procedural feel. The recipe ingredients are scattered
across the docs but they're all there:

| Primitive | What it gives us |
|-----------|------------------|
| **`vtkCommand::ModifiedEvent`** on every node | Auto-dirty propagation: observe upstream outputs, mark graph node dirty when they change |
| **`SetHideFromEditors(true)`** | Hide a node from Data module + node selectors — perfect for graph-internal intermediates |
| **`SetSaveWithScene(false)`** | Skip serialization into `.mrb` — keep intermediates ephemeral |
| **`vtkMRMLSubjectHierarchyNode.CreateFolderItem`** | Group all graph-owned MRML nodes under one folder so they DO show in Data, but neatly contained |
| **`slicer.cli.run(...)` with `completedCallback`** | Async CLI invocation; we can keep the canvas responsive and update outputs when the subprocess finishes |
| **`@parameterNodeWrapper`** | Typed Python proxy over `vtkMRMLScriptedModuleNode` — clean way to persist our graph state into `.mrb` |
| **Segment Editor effects** support `effect.setParameter(...); effect.self().onApply()` | We CAN drive Segment Editor effects from code for the deterministic-parameter ones (Threshold, Otsu, Grow from seeds) — just not for paint-mode |

The two we should adopt immediately are **hidden ephemeral nodes** and
**observer-driven dirty propagation**.

## 5. Module status table

Mapping every module/node-type we care about onto a procedural-fitness
scale:

| Module / Node type           | Fitness | Notes |
|------------------------------|---------|-------|
| Threshold (SITK)             | ✅ pure | Already procedural in our impl; could be Segment-Editor-Threshold instead but SITK is simpler |
| Gaussian Smooth (SITK)       | ✅ pure | Same |
| Median Filter (SITK)         | ✅ pure | Same |
| Crop Volume                  | ✅ near-pure | Param node + ROI; deterministic. Auto-rerun on upstream change is feasible |
| Resample Scalar Volume       | ✅ near-pure | CLI but deterministic with fixed params |
| Apply Transform              | ✅ pure | Setting reference + observing transform is enough; harden = mutating, ✗ |
| BRAINSFit Registration       | ⚠️ slow | Expensive CLI; should be async + cached aggressively; *don't* auto-rerun on every prop tweak — debounce or require explicit press-1 |
| Segment Editor — Threshold/Otsu/Margin/Logical-ops/Grow-from-seeds | ⚠️ scripted | These effects have deterministic params and can be replayed |
| Segment Editor — Paint/Erase/Scissors/Draw | ❌ stateful | Result is the user's brush history; **cannot** be procedural. Treat as terminal "editing" node where the segmentation IS the state |
| Markups — placement | ❌ stateful | Same as above |
| Volume Rendering             | 🟡 visualization-only | No data flow forward; "view of an upstream volume." Already linked-module |
| Volumes (window/level)       | 🟡 visualization-only | Same |
| Models (display)             | 🟡 visualization-only | Same |
| Layout (slice composites)    | 🟡 visualization-only | Same |
| Volume preset opacity-curve hand-tweak | ❌ stateful | Embedded display node state; treat as terminal |

Counts: out of typical clinical workflow primitives, the vast majority
(✅ + ⚠️ scripted) ARE procedurally addressable. Only the brush-style
interactive modules genuinely break the model.

## 6. Architectural recommendations

### 6.1 Hidden ephemeral output nodes

Today our wrapped nodes create MRML nodes with `AddNewNodeByClass` and
default visibility — they show up in Data and get saved with the scene.

Adopt the pattern: every graph-node-owned MRML node gets

```python
node.SetHideFromEditors(True)
node.SetSaveWithScene(False)
```

and is parented under a Subject Hierarchy folder named "Node Editor (auto)"
created once per scene. When the user *explicitly* wants to keep one (a
"materialize" or "promote" action), we flip both flags back.

**Result:** the Data module is no longer polluted with 30 stale
intermediates. Users still see the *final* output that's actively routed
to a viewer slot (we either move it out of the auto folder on slot
assignment, or just rely on the Data module's ability to expand the
folder).

### 6.2 Observer-driven dirty propagation

Right now we mark downstream nodes dirty only when their own properties
change. That misses changes happening to MRML nodes outside the graph
(e.g. the user runs a transform on an input volume from another module).

Wire each graph node's `_run_node` to:
1. Add a `ModifiedEvent` observer on every input MRML node.
2. Add a `ModifiedEvent` observer on every output MRML node we created.
3. Callback marks the graph node dirty.

This gives us true upstream-driven dirty propagation, in the
procedural-graph sense.
**One caveat:** observer callbacks have to be debounced — a single SITK
filter run fires many ModifiedEvents on its output during construction.
Coalesce within ~100 ms via `QTimer.singleShot`.

### 6.3 Async CLI with placeholder pattern

For BRAINSFit and any other slow CLI:

1. Press 1 triggers `slicer.cli.run(module, parameters=p, wait_for_completion=False, completedCallback=cb)`.
2. The output MRML node already exists (created hidden), but is empty
   ("computing…").
3. Node visually shows a "spinner" indicator (paint a small running
   stripe).
4. `completedCallback` flips the spinner off, marks downstream dirty,
   re-routes viewer if this slot is active.

This keeps the canvas interactive during long ops — which is essential
the moment registration enters a typical workflow.

### 6.4 Treat brush-mode modules as "edit-state" nodes

Don't fight Segment Editor's paint mode. Model it as:

- **SegmentEditorNode** has 1 input (volume) and 1 output (segmentation).
- The segmentation node IS the state. Editing in the module mutates it
  in place.
- Downstream consumers (e.g. a "Surface Model" node generating a model
  from the segmentation) observe the segmentation's `ModifiedEvent` and
  re-run automatically.
- "Re-execute upstream" on the Segment Editor node simply means "ensure
  the input volume is fresh"; the segmentation is preserved.
- A "Reset" affordance on the node clears the segmentation back to
  empty if the user wants to start over.

This is the compositing-graph equivalent of a `Paint` node — strokes are
persistent internal state, but the node still participates in the graph.

### 6.5 Parameter-node-backed serialization

Today we serialize the graph to free-form JSON. Move to:

- One `vtkMRMLScriptedModuleNode` per graph (with `@parameterNodeWrapper`).
- Stores: node positions, edges, per-node property values, viewer-slot
  bindings.
- References to the MRML output nodes are by ID (handled by the wrapper).

**Wins:** the graph travels in `.mrb` saves natively. Reopening a `.mrb`
restores the graph too. No separate Save/Load Graph buttons needed.

### 6.6 What NOT to attempt

- **VTK-pipeline-level integration.** MRML observers fire on `Modified`
  but Slicer's modules don't expose their VTK pipelines for direct
  reuse — each module is a one-shot computation, not a reusable filter.
  Trying to wire `vtkAlgorithm`s end-to-end across modules is a dead
  end.
- **Auto-recompute on every prop change** for slow CLI ops. Debounce
  is not enough; the user will tweak a registration sampling rate 5
  times in 3 seconds. Stick to explicit press-1 for the slow tier;
  auto-recompute only for the cheap tier.
- **A separate parallel scene.** The temptation to keep "our" nodes in
  a shadow scene is strong but doesn't pay off — too many Slicer APIs
  assume a single scene. The hidden+ephemeral pattern in §6.1 achieves
  90% of what a shadow scene would, with none of the integration tax.

## 7. Concrete next steps for our codebase

In recommended order:

1. **Hide our intermediates.** One-line change per `_remove_cached_volume` /
   `_get_or_create_output` / similar helpers — call `SetHideFromEditors(True)`
   and `SetSaveWithScene(False)`. Reparent into a "Node Editor (auto)"
   subject-hierarchy folder. Low risk, instantly cleaner UX.
2. **Observe input MRML nodes.** Add `ProcessMRMLEvents`-style observers
   when `_run_node` resolves inputs; remove them when the graph node is
   deleted or its edges change. Wire to the existing dirty mechanism with
   debouncing.
3. **Async CLI for RegistrationNode.** Move from `runSync` to `run` with
   completedCallback. Add a "computing…" badge on the node.
4. **Move serialization to parameter-node-wrapper.** Replace the JSON
   Save/Load with MRML-backed persistence so graphs travel with `.mrb`.
5. **Don't ship procedural Segment Editor.** Document that paint-mode
   results live in the segmentation node and the graph routes that
   node's identity, not its computation history.

Each of these is independent and can land separately.

## 8. Complete module enumeration (from Slicer 5.x docs)

The full module index from
[slicer.readthedocs.io/en/latest/user_guide/modules/index.html](https://slicer.readthedocs.io/en/latest/user_guide/modules/index.html),
mapped onto our procedural-fitness scale. Grouping similar modules
together where they share the same fit profile.

### 8.1 Main modules

| Module | Fit | Treatment |
|--------|-----|-----------|
| Data | 🟢 view-only | Subject Hierarchy browser; nothing to wrap. Our graph SHOULD show up here under its own folder |
| DICOM | 🟢 loader | I/O node wrapping `DICOMUtils.loadPatientByUID(...)` / similar — produces volumes |
| Markups | ❌ stateful | Placement is brush-mode; wrap as edit-state node only |
| Models | 🟡 visualization | Linked-module (already done) |
| Scene Views | 🟢 view-only | Snapshot mechanism; outside graph scope |
| Segmentations | 🟡 visualization/conversion | Linked-module (already done) |
| Segment Editor | ❌ partially stateful | Threshold/Otsu/Margin/Logical/Grow-from-seeds ARE scripted; Paint/Erase/Scissors/Draw are brush-mode |
| Welcome | — | Not a graph concern |
| Transforms | 🟡 linked | Linked-module (already done) |
| View Controllers | 🟢 view-only | Tied to view nodes — outside graph scope |
| Volume Rendering | 🟡 visualization | Linked-module (already done) |
| Volumes | 🟡 visualization | Linked-module (already done) |

### 8.2 Wizards / Informatics

| Module | Fit | Treatment |
|--------|-----|-----------|
| Compare Volumes | 🟢 layout/view | Could be a "Compare" layout node that takes 2+ volumes |
| Colors | 🟢 ref data | New port type COLOR (`vtkMRMLColorNode`) for lookup-table inputs |
| Plots | 🟢 procedural | Generate plot from table data — pure function. New port types PLOT_CHART (`vtkMRMLPlotChartNode`) and PLOT_SERIES (`vtkMRMLPlotSeriesNode`) |
| Sample Data | 🟢 loader | Already wrapped |
| Tables | 🟢 procedural | Numeric/text data, easy to wrap. New port type TABLE (`vtkMRMLTableNode`) |
| Terminologies | 🟢 ref data | Code dictionaries; unlikely to need a graph node |
| Texts | 🟢 procedural | `vtkMRMLTextNode` — useful for LLM nodes, notes, JSON params |
| DataProbe | 🟢 view-only | Live cursor info; no graph hook |

### 8.3 Registration

| Module | Fit | Treatment |
|--------|-----|-----------|
| General Registration (BRAINS) | ⚠️ slow CLI | Already wrapped (`RegistrationNode`); needs async migration |
| Resample Image / Resize Image (BRAINS) | ✅ procedural | Wrap as separate nodes; reuse output volume |
| Fiducial / Landmark Registration | 🟡 mixed | Take fiducial inputs from upstream; computation deterministic given fiducial positions |
| Reformat | 🟢 view-only | Manipulates slice node orientation; outside graph scope |
| Registration Metric Test | — | Diagnostic; skip |

### 8.4 Quantification

| Module | Fit | Treatment |
|--------|-----|-----------|
| Line Profile | ✅ procedural | Take volume + line markup → produce table |
| Segment statistics | ✅ procedural | Segmentation + volume → table of metrics |
| PET SUV | ✅ procedural | PET volume → SUV volume |

### 8.5 Sequences — major edge case

| Module | Fit | Treatment |
|--------|-----|-----------|
| Sequences | ⚠️ **new dimension** | See §10.5 |
| Crop volume sequence | ⚠️ sequence-aware | Takes a SEQUENCE input, produces a SEQUENCE output |
| MultiVolumeImporter / MultiVolumeExplorer | ⚠️ sequence-aware | Loaders for 4D data |

### 8.6 Diffusion

DWI/DTI volume types are distinct (`vtkMRMLDiffusionTensorVolumeNode`,
`vtkMRMLDiffusionWeightedVolumeNode`). They share most behavior with
scalar volumes. We can either treat as VOLUME for port-typing or add
DTI / DWI port subtypes. Punt until someone needs it.

### 8.7 Filtering — bulk of the CLI ecosystem

All members below take 1-2 scalar volumes + params and produce a scalar
volume via CLI. All are **✅ procedural with caching**:

Add/Cast/Mask/Multiply/Subtract/Threshold Scalar Volumes, Curvature/Gradient
Anisotropic Diffusion, Gaussian Blur, Grayscale Fill Hole / Grind Peak,
Median Image Filter, N4ITK Bias correction, CheckerBoard Filter, Extract
Skeleton, Histogram Matching, Image Label Combine, **Simple Filters**
(generic SITK wrapper), Voting Binary Hole Filling.

**Strategy**: rather than 20 individual nodes, build a generic
**`SimpleFilterNode`** with a filter-name property dropdown (driven by
`SimpleITK`'s registered filter list) — single class, every filter
available. Keep the dedicated Threshold/Smooth/Median nodes as
ergonomic shortcuts.

### 8.8 Surface Models — important to flag

| Module | Fit | Treatment |
|--------|-----|-----------|
| **Dynamic Modeler** | ✅ **already procedural** | See §10.4 |
| Grayscale Model Maker / Model Maker | ✅ procedural | Volume → model surface (Marching Cubes) |
| Label Map Smoothing | ✅ procedural | Labelmap → smoothed labelmap |
| Merge Models | ✅ procedural | Multiple model inputs → single model |
| Model To LabelMap | ✅ procedural | Model → labelmap volume |
| Probe Volume With Model | ✅ procedural | Volume + Model → Model with scalars |
| Surface Toolbox | ✅ procedural | Decimation / smoothing / normal generation |

### 8.9 Converters / Utilities

| Module | Fit | Treatment |
|--------|-----|-----------|
| Crop Volume | ✅ procedural | Already wrapped |
| Create a DICOM Series | 🟢 export | Save node as DICOM |
| Orient Scalar Volume | ✅ procedural | Reorient axes |
| Vector to Scalar Volume | ✅ procedural | Extract component / magnitude |
| Brain Deface / Strip Rotation / Transform Convert | ✅ procedural | All BRAINS CLI, all wrappable |
| DICOM Patcher / Endoscopy / Screen Capture | 🟢 specialist | Niche; skip unless requested |

### 8.10 Developer / Testing / Legacy

Skip all of these for graph wrapping — Event Broker, Cameras, Extension
Wizard, Performance Tests, etc. are not data-flow modules. Legacy/retired
modules also skip.

---

## 9. Counts by fitness

- **✅ pure / procedural with caching**: ~35 modules — bulk of Filtering,
  Surface Models, Quantification, Resampling, Converters
- **⚠️ slow CLI / sequence-aware**: ~5 modules — Registration (BRAINS),
  Sequences, sequence-aware filters
- **🟡 visualization / linked-module-only**: ~8 modules — Volume Rendering,
  Volumes, Models, Transforms, Segmentations, etc. (most already wrapped)
- **❌ stateful editing**: 2 — Segment Editor paint mode, Markups placement
- **🟢 view/loader/info-only, no graph wrap needed**: ~12 — Data, Welcome,
  DataProbe, Scene Views, View Controllers, etc.

So out of ~70 user-facing modules, only **2 are fundamentally non-procedural**.
The rest split cleanly into wrappable categories.

---

## 10. Edge cases to pre-plan

Things that would silently bite us if we don't design around them.

### 10.1 Subject Hierarchy is a separate tree

The SH is a tree on top of the MRML scene, made of "items" that
reference data nodes (folders are SH items with no data node). When we
park our intermediates in a "Node Editor (auto)" folder, we're creating
SH items, not MRML nodes — different API. The folder item gets a
folder display node and can be expanded/collapsed in the Data module.

**Plan:** one SH folder per graph instance, created lazily on first node
insertion; reparent every graph-owned data node under it.

### 10.2 Storage nodes are separate from data nodes

Persistent MRML data nodes (volumes, models, segmentations) have a
companion `vtkMRMLStorageNode` (one per format). Setting
`SetSaveWithScene(False)` on the data node does **not** automatically
set it on the storage node; both must be flagged or the storage node
will linger when the scene is saved.

**Plan:** helper `_mark_ephemeral(node)` that flips both flags on the
data node AND all its storage nodes; call from every spot that creates
or caches an output.

### 10.3 Display nodes per view

A single MRML data node can own multiple display nodes — one for each
view that renders it. Volume Rendering display nodes are the obvious
example; segmentations have a 2D-slice display node AND a 3D display
node. When we "hide other VRs" we should iterate display nodes for the
relevant type, not assume one-per-volume.

**Plan:** centralize visibility scoping in helpers that walk
`mrmlScene.GetNodesByClass('vtkMRMLVolumeRenderingDisplayNode')` etc.,
rather than rely on `GetFirstVolumeRenderingDisplayNode`.

### 10.4 Dynamic Modeler already does what we do

Slicer's `DynamicModeler` module is itself a "rules-based modular
geometry processing" pipeline. It's surface-mesh focused and not very
discoverable, but it's the closest existing Slicer feature to a node
graph. We should NOT compete with it — instead, wrap each Dynamic
Modeler "tool" (Plane Cut, Hollow, Boundary Cut, Append, etc.) as a
graph node that creates a Dynamic-Modeler logic node under the hood.

**Plan:** investigate `vtkSlicerDynamicModelerLogic` and consider a
`DynamicModelerNode` base class once we move into surface-mesh work.

### 10.5 Sequences = the time dimension

`vtkMRMLSequenceNode` holds a list of typed nodes (volumes, transforms,
markups, …); `vtkMRMLSequenceBrowserNode` controls "which index is
currently mirrored into the scene as a regular node." This is a
procedural compositor's time slider, basically.

The hard part: when the browser advances, the *active* scalar volume
node (which our graph nodes have cached pointers to) effectively
swaps contents. Some graph downstream nodes (display-only) want the
swap transparent; others (anything caching a result keyed on the
current frame) need a per-frame invalidation.

**Plan:**
- Add new port type **SEQUENCE** for nodes that operate frame-by-frame.
- Add a **SequenceBrowserNode** graph node that exposes a "current
  frame" property; observers fire when frame advances.
- For "per-frame" downstream nodes, observe the browser, mark
  downstream dirty on frame change.
- For "stamp once, animate the result" downstream nodes (e.g.
  Volume Rendering), no change — they read the active node which the
  browser keeps swapping.

Punt actual implementation until someone has a 4D dataset to demo with.

### 10.6 Singleton nodes

Some MRML nodes are singletons by class — only one per scene. Examples:
- `vtkMRMLSelectionNode` — current selected node
- `vtkMRMLInteractionNode` — current interaction mode
- `vtkMRMLLayoutNode` — current view layout
- `vtkMRMLAppLogicNode`

We already poke `vtkMRMLLayoutNode` indirectly through the layout
manager. **Plan:** keep poking it but never try to instance it — and
never put it under our "Node Editor (auto)" folder.

### 10.7 Node references / reference roles

MRML nodes wire themselves together with **typed references** (a node
can have a "display" role with multiple display-node IDs, a "transform"
role with one transform-node ID, etc.). These are completely separate
from our graph edges. The user-visible MRML scene is itself a directed
graph; ours is a parallel layer.

**Plan:** never confuse the two. Our edges drive *recomputation*; MRML
references drive *display and persistence*. They can both exist on the
same nodes and that's fine.

### 10.8 MRML scene Clear() / Close events

When the user does File → Close Scene or File → New, `mrmlScene.Clear()`
fires. Every node reference we hold becomes dangling.

**Plan:** observe `vtkMRMLScene.StartCloseEvent` and `EndCloseEvent`.
On Close, either clear our graph too OR mark all cached outputs as
needing re-execution. Probably the former — keeping a graph alive
across scene Close is more confusing than helpful.

### 10.9 Multiple display nodes on segmentations

Segmentations have a 2D display node (for slice overlay) AND a 3D
display node (for surface in 3D view). They're independent — toggling
one doesn't affect the other. Our visibility scoping needs to remember
this.

### 10.10 Slice composite layers (background / foreground / label)

Each slice view has THREE volume slots: background, foreground (with
opacity), label (with alpha). We currently only set background. Some
workflows want a volume as foreground over a different background.

**Plan:** add a `slot` property on viewer-route operations (default
"background", optional "foreground" / "label").

### 10.11 Reentrance: native module widget vs graph node

When the user double-clicks a Volume Rendering node, we switch Slicer
to the VR module. They then tweak the opacity transfer function by
hand. Their tweaks fire `ModifiedEvent` on the display node we're
observing. Our graph node sees its output modified and marks downstream
dirty — but the **input** didn't change, so re-executing would clobber
the user's hand-tweak.

**Plan:** distinguish "output changed because we re-ran" from "output
changed because the user edited it." Use an instance flag set just
before our `execute()` writes the output:

```python
self._self_modified = True
try:
    do_work()
finally:
    self._self_modified = False
```

In the observer callback, ignore Modified events while `_self_modified`
is set. Outside our re-execution window, a Modified means the user
edited it — treat that as the new ground truth and DO mark downstream
dirty (because downstream sees a changed value), but do NOT re-execute
the current node.

### 10.12 Plot / Table / Text data are first-class

`vtkMRMLPlotChartNode`, `vtkMRMLTableNode`, `vtkMRMLTextNode`,
`vtkMRMLColorNode` all live in the MRML scene alongside volumes. We
should add port types for them now (cheap: just strings) so future
nodes (Segment Statistics → Table → Plot) can connect them. Doing it
early is much cheaper than retrofitting.

**Plan:** add `TABLE`, `PLOT`, `TEXT`, `COLOR` to `base_node.py` port
constants and `PORT_COLORS` in `constants.py`.

### 10.13 DICOM is a database, not a file

The DICOM module wraps `ctkDICOMDatabase`. Loading a study isn't a
simple file read — it's a query against the local database (which may
also include remote PACS connections). A "DICOM Loader" graph node
needs a property for the study UID (or patient name) rather than a
file path.

---

**Sources used while writing this analysis**

- [MRML Overview — 3D Slicer docs](https://slicer.readthedocs.io/en/latest/developer_guide/mrml_overview.html)
- [`vtkMRMLNode.h` — Slicer source](https://github.com/Slicer/Slicer/blob/main/Libs/MRML/Core/vtkMRMLNode.h)
- [Slicer Script Repository](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html)
- [Using Segment Editor effects programmatically — Slicer Discourse](https://discourse.slicer.org/t/using-segment-editor-effects-programmatically/11561)
- [`slicer/cli.py` — Slicer source](https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/cli.py)
- [Slicer Python FAQ](https://slicer.readthedocs.io/en/latest/developer_guide/python_faq.html)
- [Slicer modules index — user guide](https://slicer.readthedocs.io/en/latest/user_guide/modules/index.html)
- [Sequences module — user guide](https://slicer.readthedocs.io/en/latest/user_guide/modules/sequences.html)
- [`vtkMRMLSequenceBrowserNode.h` — Slicer source](https://github.com/Slicer/Slicer/blob/main/Modules/Loadable/Sequences/MRML/vtkMRMLSequenceBrowserNode.h)
- Local cache: `docs/slicer_api_cache/`
