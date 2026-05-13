# Procedural Workflow in Slicer — Roadblocks and Levers

A deep-dive comparing Nuke's evaluation model against Slicer's MRML/module
architecture, with concrete recommendations for our node graph.

## 1. Nuke's model in one paragraph

Every Nuke node is a pure-ish function from inputs (image+metadata streams)
to outputs. Nodes are nodes — there is no separate "scene." Evaluation is
**lazy and pull-based**: the viewer asks the active node for pixels at a
given frame; that node asks its inputs; the chain rolls upstream until a
read node or a cached value satisfies the request. A knob change marks
the touched node dirty and bumps a hash; any downstream pull recomputes.
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

The mismatch is structural: Nuke nodes own their output, Slicer modules
edit shared scene state.

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
is "procedural" in the Nuke sense (each evaluation lives in its own
cache slot).

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

This gives us true upstream-driven dirty propagation, in the Nuke sense.
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

This is the Nuke equivalent of a `Paint` node — strokes are persistent
internal state, but the node still participates in the graph.

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

---

**Sources used while writing this analysis**

- [MRML Overview — 3D Slicer docs](https://slicer.readthedocs.io/en/latest/developer_guide/mrml_overview.html)
- [`vtkMRMLNode.h` — Slicer source](https://github.com/Slicer/Slicer/blob/main/Libs/MRML/Core/vtkMRMLNode.h)
- [Slicer Script Repository](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html)
- [Using Segment Editor effects programmatically — Slicer Discourse](https://discourse.slicer.org/t/using-segment-editor-effects-programmatically/11561)
- [`slicer/cli.py` — Slicer source](https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/cli.py)
- [Slicer Python FAQ](https://slicer.readthedocs.io/en/latest/developer_guide/python_faq.html)
- Local cache: `docs/slicer_api_cache/` (extracted via `tools/ask_gemma.ps1`)
