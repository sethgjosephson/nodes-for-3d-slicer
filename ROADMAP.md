# Roadmap: Nodes for 3D Slicer

## Phase 1 — Foundation (current)
Core graph infrastructure working inside Slicer.

- [x] Project scaffold and CMakeLists extension structure
- [ ] NodeGraphQt installs cleanly via `slicer.util.pip_install`
- [ ] Canvas embeds in Slicer's module panel without crashing
- [ ] Load Volume node loads a .nrrd/.nii.gz and outputs a vtkMRMLScalarVolumeNode
- [ ] Threshold node applies a SimpleITK binary threshold
- [ ] Executor walks a 3-node graph (Load → Threshold → Save) successfully
- [ ] Graph saves/loads to JSON

## Phase 2 — Node Library Expansion
Wrap the most-used Slicer tools as nodes.

- [ ] Gaussian Smooth, Median Filter, Edge Detection filter nodes
- [ ] Label Map to Segmentation conversion node
- [ ] Grow from Seeds segmentation node (Segment Editor effect)
- [ ] BrainsFit rigid/affine registration node
- [ ] Apply Transform node
- [ ] Volume Rendering node with preset picker
- [ ] Slice viewer node (controls 2D slice display)
- [ ] Crop Volume node
- [ ] Surface model generation (Marching Cubes) node

## Phase 3 — UX Polish
Make the experience feel like Nuke.

- [ ] Typed port colors (red=Volume, blue=Segmentation, gold=Transform, green=Model)
- [ ] Port type validation — reject incompatible connections with visual feedback
- [ ] Node properties panel (right-click → Properties) shows all parameters
- [ ] Node search popup (Tab key) like Nuke's node browser
- [ ] Node groups / backdrop boxes for annotation
- [ ] Minimap for large graphs
- [ ] Undo/redo stack

## Phase 4 — Scene Integration
Tie the graph to Slicer's MRML scene lifecycle.

- [ ] Graph state serializes into `vtkMRMLScriptedModuleNode` → travels with .mrb
- [ ] MRML scene observer: dropping a volume node onto the canvas auto-creates a Load node
- [ ] "Dirty" node highlighting when upstream data changes
- [ ] Incremental execution: only re-run nodes downstream of changed inputs

## Phase 5 — Advanced Nodes
Power-user and research features.

- [ ] Python Script node (inline code editor, arbitrary logic)
- [ ] CLI Module node (generic wrapper for any installed Slicer CLI)
- [ ] Batch process node (iterate over a folder of volumes)
- [ ] Jupyter notebook export (graph → runnable .ipynb)
- [ ] EEG/surface overlay node
- [ ] DICOM import node

## Phase 6 — Distribution
Package and publish.

- [ ] Extension Manager submission (Extensions Index PR)
- [ ] CI: GitHub Actions running Slicer headless tests
- [ ] Documentation site
- [ ] Demo video
