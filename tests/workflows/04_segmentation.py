# Segment by threshold and by Otsu, hand the result to the Segment Editor
# and Segmentations nodes, then change the source.
import numpy as np

g = G(editor)
g.clear()


def segment_voxels(seg, index=0):
    sid = seg.GetSegmentation().GetNthSegmentID(index)
    arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg, sid)
    return int((arr > 0).sum())


section("Sample Data -> Segmentation (threshold)")
src = g.add('SampleDataNode', sample='MRHead')
segn = g.add('SegmentationNode', method='Threshold', lower=60.0, upper=279.0)
g.chain(src, segn)
g.select(segn)
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
seg = g.out(segn, 'seg_out')
check(seg is not None, "segmentation exists")
n_thresh = segment_voxels(seg) if seg else 0
vol = g.out(src, 'volume_out')
a = array(vol)
expected = int(((a >= 60) & (a <= 279)).sum())
check(seg.GetSegmentation().GetNumberOfSegments() == 1, "one segment")
check(abs(n_thresh - expected) <= expected * 0.001,
      f"segment matches the threshold range ({n_thresh} vs {expected})")
check(len(slicer.util.getNodesByClass('vtkMRMLSegmentEditorNode')) == 0,
      "no temporary segment editor node left behind")
screenshot("threshold_segmentation")

section("change the range and run again")
g.set(segn, 'lower', 120.0)
g.select(segn)
g.press('1')
check(g.out(segn, 'seg_out').GetID() == seg.GetID(),
      "same segmentation node reused")
check(seg.GetSegmentation().GetNumberOfSegments() == 1, "still one segment")
n2 = segment_voxels(seg)
expected2 = int(((a >= 120) & (a <= 279)).sum())
check(abs(n2 - expected2) <= expected2 * 0.001,
      f"segment follows the new range ({n2} vs {expected2})")

section("Otsu")
g.set(segn, 'method', 'Otsu')
g.select(segn)
g.press('1')
check(not g.errors(), f"no errors ({g.errors()})")
n3 = segment_voxels(seg)
check(0 < n3 < a.size and n3 != n2, f"Otsu gives a different mask ({n3})")

section("Segment Editor and Segmentations nodes pass it on")
sed = g.add('SegmentEditorNode', x=250, y=280)
g.connect(src, 'volume_out', sed, 'volume_in')
g.connect(segn, 'seg_out', sed, 'seg_in')
segs = g.add('SegmentationsNode', x=250, y=420)
g.connect(sed, 'seg_out', segs, 'seg_in')
g.select(segs)
g.press('2')
check(not g.errors(), f"no errors ({g.errors()})")
check(g.out(segs, 'seg_out') is not None
      and g.out(segs, 'seg_out').GetID() == seg.GetID(),
      "the same segmentation flows through both wrapper nodes")

section("double-click opens the linked module on the data")
editor._on_node_selected(sed)
wait(500)
check(slicer.util.selectedModule() == 'SegmentEditor',
      f"Segment Editor module is shown ({slicer.util.selectedModule()})")
w = slicer.modules.SegmentEditorWidget.editor
check(w.segmentationNode() is not None
      and w.segmentationNode().GetID() == seg.GetID(),
      "Segment Editor points at the segmentation from the graph")
check(w.sourceVolumeNode() is not None
      and w.sourceVolumeNode().GetID() == vol.GetID(),
      "Segment Editor points at the source volume")
screenshot("segment_editor_linked")
slicer.util.selectModule('SlicerNodeEditor')
wait(300)

section("hand edit, then check the badges")
sid = seg.GetSegmentation().GetNthSegmentID(0)
arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg, sid, vol)
arr[:] = 0
arr[10:20, 10:20, 10:20] = 1
slicer.util.updateSegmentBinaryLabelmapFromArray(arr, seg, sid, vol)
wait(500)
check('Segmentations' in g.dirty(),
      f"editing the segment marks the downstream wrapper dirty ({g.dirty()})")
check(sed.node_data.stale_input,
      "Segment Editor node shows the stale input badge")

section("deleting wrapper nodes does not delete upstream data")
g.select(segs)
g.press('Del')
check(mrml_exists(seg), "deleting a wrapper node keeps the segmentation")
g.select(segn)
g.press('Del')
check(not mrml_exists(seg), "deleting the Segmentation node removes it")
check(mrml_exists(vol), "source volume is still there")

g.finish()
