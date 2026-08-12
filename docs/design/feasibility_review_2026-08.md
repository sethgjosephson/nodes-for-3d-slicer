# Feasibility Review (August 2026)

A code-level review of the project's viability before the next development
push. Verdict up front: the project is feasible, and the riskiest technical
bets are already retired. The remaining risks are correctness at the edges,
memory growth, and maintenance surface, not whether the core idea holds.

## What is already de-risked

- The custom QGraphicsScene engine runs on PythonQt, which was the single
  riskiest bet. The known binding quirks are documented and worked around.
- Roughly 15 node types run end to end, including linked-module nodes that
  reuse Slicer's native widgets.
- Dirty propagation via MRML ModifiedEvent observers, MRML hygiene
  (ephemeral outputs grouped under a Subject Hierarchy folder), scene-close
  survival, and async CLI execution all exist and work.
- Graph persistence works twice over: standalone JSON files, plus a tagged
  `vtkMRMLScriptedModuleNode` carrier so the graph travels inside `.mrb`
  saves and restores on import.

## The one deep conceptual risk: edit-state nodes

The design analysis correctly notes that only two module families are
fundamentally non-procedural (interactive segmentation editing and markup
placement). The count is right but undersells the exposure: those two are
among the most-used interactive tools in real Slicer workflows.

The consequence to design for is **stale geometry under edit-state nodes**.
If the user hand-edits a segmentation, then changes an upstream crop or
re-runs a registration, the graph re-cooks the volume but the hand-edited
segmentation cannot be recomputed. It now sits on the wrong voxel grid or
in the wrong coordinate frame, and the graph silently presents a lie.

Mitigation shipped with this review: edit-state nodes (Segment Editor,
Markups) carry an `EDIT_STATE` flag. When an upstream input changes under
one, the node shows an amber warning badge instead of pretending it can
re-cook. Double-clicking the node (opening its editor) acknowledges and
clears the warning. Future work: offer to resample or transform the edited
data forward when the upstream geometry change is a known transform.

## Correctness defects found and fixed

1. **Async execution poisoned the first downstream cook.** The executor
   marked a node clean immediately after `execute()` returned, but async
   nodes (Registration) return placeholder outputs while the CLI runs.
   Downstream nodes then executed against empty volumes and were marked
   clean. Fixed: the executor now recognises in-flight async work, leaves
   the node dirty, and blocks its descendants for that pass. The completion
   callback marks the node clean, dirties downstream, and re-cooks the
   active viewer slot.

2. **A failed node did not halt its descendants.** An exception in one
   node's `execute()` showed an error dialog, but the topological walk kept
   going, running descendants against stale or missing inputs and marking
   them clean. Fixed: a failure marks the node with an error badge and
   blocks everything downstream of it for that pass.

3. **Apply Transform mutated its input.** The node set the transform on the
   upstream volume and returned that same volume, so every other consumer
   of the upstream data saw it transformed, and harden mode destructively
   resampled shared data. Fixed: the node now copies the input into an
   output it owns and applies the transform to the copy.

4. **Re-runs falsely re-dirtied downstream nodes.** During a pipeline pass,
   an upstream node's write fires the observer a downstream node bound on
   the previous run. The debounced callback lands after the pass finishes,
   marking freshly-cleaned nodes dirty again. Fixed: the observer callback
   now also checks whether the upstream graph node is inside its own
   `execute()`; graph-internal writes no longer schedule dirty marks.
   External edits (other modules, scripts, hand edits) are still detected.

## Sustainability risks (open, budgeted for)

- **Memory.** Every intermediate output is a full volume copy. A large CT
  through a six-node chain holds gigabytes of intermediates. A cache
  eviction policy will eventually be needed (for example: keep cooked
  outputs only for nodes routed to viewer slots, recompute interior nodes
  on demand). Note the interaction with input observers, which hold
  pointers to cached MRML nodes.
- **PythonQt fragility.** The engine works, but every new UI feature risks
  a new binding quirk. The compatibility shim's claim of PySide support is
  untested and should not be relied on.
- **Linked-module setter coupling.** `INPUT_SETTERS` probes Slicer widget
  method names at runtime and fails silently by design. A Slicer point
  release can quietly break linked modules. The debug environment variable
  `SLICER_NODE_EDITOR_DEBUG=1` now logs every swallowed setter miss and
  observer failure so upgrades can be smoke-checked quickly.
- **Serialization is the public API.** Saveable workflows are the
  deliverable, so the graph file format matters. The format now carries a
  `version` field and nodes serialise a stable `type` identifier resolved
  through a registry, decoupled from Python class names. Legacy files
  (class + module fields) still load.

## Scope guidance

- The generic SimpleFilter node remains the highest-leverage roadmap item:
  one class replaces roughly 18 hand-written CLI wrappers.
- 4D sequence support is a complexity multiplier; keep it deferred until a
  real 4D dataset drives the design.
- Before an Extensions Index submission, write the comparison paragraph
  against existing pipeline-style extensions (for example Kitware's
  SlicerPipelines). This project is differentiated by the interactive
  canvas, viewer-slot routing, and linked native module widgets.

## Verification

Module self-tests cover scene creation, node placement, edge connection,
pipeline execution with a synthetic volume, executor failure isolation,
and a serialisation round trip. Run them from the Reload & Test section
of the module panel, or from the Python console:

```python
slicer.util.selectModule('SlicerNodeEditor')
import SlicerNodeEditor
SlicerNodeEditor.SlicerNodeEditorTest().runTest()
```
