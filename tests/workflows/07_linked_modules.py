# Double-clicking a wrapper node opens its Slicer module on the node's data.
# Two sources are loaded so the module cannot be right by accident.
g = G(editor)
g.clear()


def current_node(module, selector):
    mw = getattr(slicer.modules, module.lower()).widgetRepresentation()
    for cls in ('qMRMLSubjectHierarchyTreeView', 'qMRMLNodeComboBox'):
        for w in mw.findChildren(cls):
            if w.objectName == selector:
                return w.currentNode()
    raise KeyError(selector)


def open_node(item):
    """What a double-click on the node does."""
    editor._on_node_selected(item)
    wait(500)


section("build two branches")
decoy = g.add('SampleDataNode', x=-400, y=0, sample='CTChest')
src = g.add('SampleDataNode', x=0, y=0, sample='MRHead')
smooth = g.add('GaussianSmoothNode', x=0, y=140, sigma=1.0)
vols = g.add('VolumesNode', x=0, y=280)
vr = g.add('VolumeRenderingNode', x=250, y=280)
g.connect(src, 'volume_out', smooth, 'volume_in')
g.connect(smooth, 'volume_out', vols, 'volume_in')
g.connect(smooth, 'volume_out', vr, 'volume_in')
segn = g.add('SegmentationNode', x=-250, y=140, lower=60.0, upper=279.0)
g.connect(src, 'volume_out', segn, 'volume_in')
segs = g.add('SegmentationsNode', x=-250, y=280)
g.connect(segn, 'seg_out', segs, 'seg_in')
decoy_seg = g.add('SegmentationNode', x=-400, y=140, lower=0.0, upper=500.0)
g.connect(decoy, 'volume_out', decoy_seg, 'volume_in')
editor._on_execute_all()
wait(500)
check(not g.errors(), f"no errors ({g.errors()})")
smooth_vol = g.out(smooth, 'volume_out')
seg = g.out(segn, 'seg_out')

section("Volumes")
open_node(vols)
check(slicer.util.selectedModule() == 'Volumes', "Volumes module shown")
n = current_node('Volumes', 'ActiveVolumeNodeSelector')
check(n is not None and n.GetID() == smooth_vol.GetID(),
      f"Volumes shows the smoothed volume ({n.GetName() if n else None})")

section("Volume Rendering")
open_node(vr)
check(slicer.util.selectedModule() == 'VolumeRendering',
      "Volume Rendering module shown")
n = current_node('VolumeRendering', 'VolumeNodeSelector')
check(n is not None and n.GetID() == smooth_vol.GetID(),
      f"Volume Rendering shows the smoothed volume "
      f"({n.GetName() if n else None})")

section("Segmentations")
open_node(segs)
check(slicer.util.selectedModule() == 'Segmentations',
      "Segmentations module shown")
n = current_node('Segmentations', 'MRMLNodeSelector_Segmentation')
check(n is not None and n.GetID() == seg.GetID(),
      f"Segmentations shows the right segmentation "
      f"({n.GetName() if n else None})")

section("a node with a properties form brings the Node Editor back")
open_node(smooth)
check(slicer.util.selectedModule() == 'SlicerNodeEditor',
      "Node Editor module shown")
check(not editor._props_collapsible.collapsed, "properties panel is open")
spin = editor._props_collapsible.findChildren('QDoubleSpinBox')
check(len(spin) == 1 and abs(spin[0].value - 1.0) < 1e-9,
      "sigma spin box shows the value")
g.select(vols)
g.press('1')
before = array(smooth_vol).astype(float).std()
spin[0].setValue(3.0)
wait(1500)
check(float(smooth.node_data.get_property('sigma')) == 3.0,
      "the spin box changed the property")
after = array(g.out(smooth, 'volume_out')).astype(float).std()
check(after < before, "the viewed chain re-ran with the new sigma")
screenshot("properties_panel")

g.finish()
