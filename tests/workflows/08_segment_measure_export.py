# Segment -> refine -> measure -> export, and segmentation -> surface -> export.
import csv
import os

import numpy as np

g = G(editor)
g.clear()


def voxels(seg, index=0, ref=None):
    sid = seg.GetSegmentation().GetNthSegmentID(index)
    return slicer.util.arrayFromSegmentBinaryLabelmap(seg, sid, ref) > 0


section("MRBrainTumor1 -> Segmentation -> Keep Largest Island -> Closing")
src = g.add('SampleDataNode', sample='MRBrainTumor1')
segn = g.add('SegmentationNode', method='Threshold', lower=90.0, upper=5000.0)
island = g.add('SegmentFilterNode', operation='Keep Largest Island')
close = g.add('SegmentFilterNode', operation='Smooth (Closing)', size_mm=3.0)
g.chain(src, segn, island, close)
g.select(close)
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
vol = g.out(src, 'volume_out')
seg0 = g.out(segn, 'seg_out')
seg1 = g.out(island, 'seg_out')
seg2 = g.out(close, 'seg_out')
check(len({seg0.GetID(), seg1.GetID(), seg2.GetID()}) == 3,
      "each filter owns its own segmentation")
n0 = int(voxels(seg0, ref=vol).sum())
n1 = int(voxels(seg1, ref=vol).sum())
n2 = int(voxels(seg2, ref=vol).sum())
print(f"  threshold {n0}  largest island {n1}  closed {n2}")
check(0 < n1 < n0, "keeping the largest island removes voxels")
check(n2 >= n1, "closing does not remove voxels")
import SimpleITK as sitk
cc = sitk.ConnectedComponent(sitk.GetImageFromArray(
    voxels(seg1, ref=vol).astype(np.uint8)))
check(int(sitk.GetArrayFromImage(cc).max()) == 1,
      "one connected island remains")
check(int(voxels(seg0, ref=vol).sum()) == n0,
      "the input segmentation is unchanged")
check(seg1.GetSegmentation().GetNthSegment(0).GetName()
      == seg0.GetSegmentation().GetNthSegment(0).GetName(),
      "segment names carry over")
screenshot("refined_segmentation")

section("every operation runs")
from Nodes.segment_ops_nodes import SEGMENT_OPERATIONS
probe = g.add('SegmentFilterNode', x=260, y=280)
g.connect(island, 'seg_out', probe, 'seg_in')
counts = {}
for name in SEGMENT_OPERATIONS:
    g.set(probe, 'operation', name)
    g.select(probe)
    g.press('2')
    err = g.error(probe)
    counts[name] = int(voxels(g.out(probe, 'seg_out'), ref=vol).sum())
    check(err is None and counts[name] > 0, f"{name}: {counts[name]} voxels")
check(counts['Grow'] > n1 > counts['Shrink'], "grow adds and shrink removes")
check(counts['Fill Holes'] >= n1, "fill holes does not remove voxels")
g.select(probe)
g.press('Del')

section("Segment Statistics -> table")
stats = g.add('SegmentStatisticsNode', x=-260, y=560)
g.connect(close, 'seg_out', stats, 'seg_in')
g.connect(src, 'volume_out', stats, 'volume_in')
g.select(stats)
g.press('3')
check(not g.errors(), f"no errors ({g.errors()})")
table = g.out(stats, 'table_out')
check(table is not None and table.GetNumberOfRows() == 1,
      "one row for one segment")
columns = [table.GetColumnName(i) for i in range(table.GetNumberOfColumns())]
print(f"  columns: {columns}")
vox_col = [c for c in columns if 'Voxel count' in c]
check(bool(vox_col), "table has a voxel count column")
if vox_col:
    reported = int(float(table.GetCellText(0, columns.index(vox_col[0]))))
    check(reported == n2,
          f"voxel count matches the segment ({reported} vs {n2})")
check(any('Mean' in c for c in columns),
      "intensity statistics are present (volume connected)")
check(slicer.app.layoutManager().layout
      == slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpTableView,
      "viewing the node shows the table layout")
screenshot("statistics_table")

section("Surface Model -> Models")
surf = g.add('SurfaceModelNode', x=0, y=560, smoothing=0.5)
g.connect(close, 'seg_out', surf, 'seg_in')
models = g.add('ModelsNode', x=0, y=700)
g.connect(surf, 'model_out', models, 'model_in')
g.select(models)
g.press('4')
check(not g.errors(), f"no errors ({g.errors()})")
model = g.out(surf, 'model_out')
points = model.GetPolyData().GetNumberOfPoints() if model else 0
check(points > 100, f"surface has points ({points})")
check(g.out(models, 'model_out') is not None
      and g.out(models, 'model_out').GetID() == model.GetID(),
      "Models wrapper passes the model on")
check(seg2.GetSegmentation().GetConversionParameter('Smoothing factor')
      != '0.123', "sanity")
before_param = seg2.GetSegmentation().GetConversionParameter(
    'Smoothing factor')
g.set(surf, 'decimation', 0.8)
g.select(models)
g.press('4')
points_dec = g.out(surf, 'model_out').GetPolyData().GetNumberOfPoints()
check(points_dec < points, f"decimation reduces points ({points_dec})")
check(g.out(surf, 'model_out').GetID() == model.GetID(),
      "the model node is reused")
check(seg2.GetSegmentation().GetConversionParameter('Smoothing factor')
      == before_param, "the input segmentation settings are untouched")
editor._on_node_selected(models)
wait(500)
check(slicer.util.selectedModule() == 'Models', "Models module shown")
mw = slicer.modules.models.widgetRepresentation()
tree = [w for w in mw.findChildren('qMRMLSubjectHierarchyTreeView')
        if w.objectName == 'SubjectHierarchyTreeView'][0]
check(tree.currentNode() is not None
      and tree.currentNode().GetID() == model.GetID(),
      "Models module shows the surface")
slicer.util.selectModule('SlicerNodeEditor')
screenshot("surface_model")

section("Mask Volume")
mask = g.add('MaskVolumeNode', x=260, y=560, fill=0.0)
g.connect(src, 'volume_out', mask, 'volume_in')
g.connect(close, 'seg_out', mask, 'seg_in')
g.select(mask)
g.press('5')
check(not g.errors(), f"no errors ({g.errors()})")
masked = array(g.out(mask, 'volume_out'))
inside = voxels(seg2, ref=vol)
check(masked.shape == array(vol).shape, "masked volume keeps the grid")
check((masked[~inside] == 0).all(), "outside the segment is the fill value")
check((masked[inside] == array(vol)[inside]).all(),
      "inside the segment is unchanged")
g.set(mask, 'invert', True)
wait(1500)
masked = array(g.out(mask, 'volume_out'))
check((masked[inside] == 0).all(), "Keep Outside blanks the inside")

section("Label Map to Segmentation")
lab = g.add('ThresholdNode', x=520, y=140, mode='Binary mask',
            lower=90.0, upper=5000.0, inside=3)
g.connect(src, 'volume_out', lab, 'volume_in')
to_seg = g.add('LabelMapToSegmentationNode', x=520, y=280)
g.connect(lab, 'volume_out', to_seg, 'volume_in')
g.select(to_seg)
g.press('6')
check(not g.errors(), f"no errors ({g.errors()})")
lab_seg = g.out(to_seg, 'seg_out')
check(lab_seg is not None
      and lab_seg.GetSegmentation().GetNumberOfSegments() == 1,
      "one segment for one label value")
check(int(voxels(lab_seg, ref=vol).sum()) == n0,
      "the segment matches the label voxels")
bad = g.add('LabelMapToSegmentationNode', x=780, y=280)
g.connect(src, 'volume_out', bad, 'volume_in')
g.select(bad)
orig = slicer.util.errorDisplay
slicer.util.errorDisplay = lambda *a, **k: None
try:
    g.press('7')
finally:
    slicer.util.errorDisplay = orig
check(g.error(bad) is not None and 'label map' in g.error(bad),
      "a grayscale volume is refused with a clear message")
g.select(bad)
g.press('Del')

section("export: table, model, segmentation, volume")
exports = {
    'stats.csv': (stats, 'table_out'),
    'tumor_surface.stl': (surf, 'model_out'),
    'tumor.seg.nrrd': (close, 'seg_out'),
    'masked.nrrd': (mask, 'volume_out'),
}
savers = []
for i, (fname, (node, port)) in enumerate(exports.items()):
    path = os.path.join(OUT_DIR, fname)
    if os.path.exists(path):
        os.remove(path)
    saver = g.add('SaveDataNode', x=-520 + 260 * i, y=860, file_path=path)
    g.connect(node, port, saver, 'data_in')
    savers.append((saver, path))
editor._on_execute_all()
wait(500)
check(not g.errors(), f"no errors ({g.errors()})")
for saver, path in savers:
    check(os.path.exists(path) and os.path.getsize(path) > 0,
          f"wrote {os.path.basename(path)} "
          f"({os.path.getsize(path) if os.path.exists(path) else 0} bytes)")
with open(os.path.join(OUT_DIR, 'stats.csv')) as f:
    rows = list(csv.reader(f))
check(len(rows) == 2, "CSV has a header and one row")

section("save the graph, clear, load, run it all again")
graph_path = g.save(os.path.join(OUT_DIR, 'segment_measure_export.json'))
n_nodes = len(g.scene.all_node_items())
n_edges = len(g.scene._edges)
editor._on_clear()
wait(300)
check(len(slicer.util.getNodesByClass('vtkMRMLSegmentationNode')) == 0,
      "Clear removed every segmentation")
check(len(slicer.util.getNodesByClass('vtkMRMLTableNode')) == 0,
      "Clear removed the table")
for _saver, path in savers:
    os.remove(path)
g.load(graph_path)
check(len(g.scene.all_node_items()) == n_nodes
      and len(g.scene._edges) == n_edges,
      f"graph loaded ({n_nodes} nodes, {n_edges} edges)")
editor._on_execute_all()
wait(500)
check(not g.errors(), f"no errors ({g.errors()})")
check(not g.dirty(), f"everything ran ({g.dirty()})")
for _saver, path in savers:
    check(os.path.exists(path) and os.path.getsize(path) > 0,
          f"wrote {os.path.basename(path)} again")

g.finish()
