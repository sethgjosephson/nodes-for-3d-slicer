"""I/O nodes: load and save volumes from/to disk, and module-linked I/O wrappers."""

import slicer
from .base_node import (SlicerBaseNode, LinkedModuleNode,
                         VOLUME, MARKUP, _mark_ephemeral)


def _snapshot_scene_node_ids():
    """Return the IDs of every MRML node currently in the scene."""
    ids = []
    for i in range(slicer.mrmlScene.GetNumberOfNodes()):
        n = slicer.mrmlScene.GetNthNode(i)
        if n is not None:
            ids.append(n.GetID())
    return ids


def _remove_one_node(node):
    """Remove a single MRML node, cleaning up its VR display nodes first."""
    try:
        try:
            vr_logic = slicer.modules.volumerendering.logic()
            dn = vr_logic.GetFirstVolumeRenderingDisplayNode(node)
            while dn is not None:
                slicer.mrmlScene.RemoveNode(dn)
                dn = vr_logic.GetFirstVolumeRenderingDisplayNode(node)
        except Exception:
            pass
        slicer.mrmlScene.RemoveNode(node)
    except Exception:
        pass


def _cleanup_loaded_nodes(node):
    """Remove every MRML node tracked on `node._loaded_node_ids`."""
    ids = getattr(node, '_loaded_node_ids', None) or []
    for node_id in reversed(ids):
        mrml_node = slicer.mrmlScene.GetNodeByID(node_id)
        if mrml_node is not None:
            _remove_one_node(mrml_node)
    node._loaded_node_ids = []
    # Also clear primary cache pointer
    node._cache.pop('volume_out', None)


def _remove_cached_volume(node, port_name):
    """
    Remove the MRML volume cached at `port_name` (single-node case).
    For multi-node loaders (Sample Data sets), use _cleanup_loaded_nodes.
    """
    old = node._cache.get(port_name)
    if old is not None:
        try:
            if slicer.mrmlScene.GetNodeByID(old.GetID()) is not None:
                _remove_one_node(old)
        except Exception:
            pass
    node._cache.pop(port_name, None)


class SampleDataNode(SlicerBaseNode):
    """Download and load one of Slicer's built-in sample volumes."""

    NODE_NAME    = "Sample Data"
    CATEGORY     = "I/O"

    INPUT_PORTS  = []
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'sample', 'label': 'Sample', 'type': 'enum',
         'default': 'MRHead',
         'items': [
             'MRHead',
             'CTChest',
             'CTACardio',
             'CTLiver',
             'CTACerebralAngiogram',
             'MRBrainTumor1',
             'MRBrainTumor2',
             'MRUSProstate',
             'MRChest',
         ]},
    ]

    def execute(self, inputs):
        import SampleData
        # Remove EVERY MRML node loaded by the previous sample (some samples
        # like the prostate set load multiple volumes / segmentations).
        _cleanup_loaded_nodes(self)

        name   = self.get_property('sample')
        logic  = SampleData.SampleDataLogic()

        before = set(_snapshot_scene_node_ids())
        primary = logic.downloadSample(name)
        if primary is None:
            raise RuntimeError(f"Sample Data: '{name}' could not be downloaded.")
        after  = _snapshot_scene_node_ids()

        # Track every node that appeared during the download
        self._loaded_node_ids = [nid for nid in after if nid not in before]

        # Mark every loaded node as graph-owned (group under SH folder,
        # skip .mrb persistence). Multi-file samples can load volumes,
        # segmentations, transforms, markups; we process them all.
        for nid in self._loaded_node_ids:
            n = slicer.mrmlScene.GetNodeByID(nid)
            if n is not None:
                _mark_ephemeral(n)

        return {'volume_out': primary}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            _route_volume_to_slices(node)


class LoadVolumeNode(SlicerBaseNode):
    NODE_NAME    = "Load Volume"
    CATEGORY     = "I/O"

    INPUT_PORTS  = []
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    PROPERTIES = [
        {'name': 'file_path', 'label': 'File Path', 'type': 'str', 'default': ''},
    ]

    def execute(self, inputs):
        path = self.get_property('file_path')
        if not path:
            raise ValueError("Load Volume: no file path specified.")
        # Remove the previously-loaded volume so we don't accumulate
        _remove_cached_volume(self, 'volume_out')
        node = slicer.util.loadVolume(path)
        _mark_ephemeral(node)
        return {'volume_out': node}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            _route_volume_to_slices(node)


class SaveVolumeNode(SlicerBaseNode):
    NODE_NAME    = "Save Volume"
    CATEGORY     = "I/O"

    INPUT_PORTS  = [("volume_in", "Volume", VOLUME)]
    OUTPUT_PORTS = []

    PROPERTIES = [
        {'name': 'file_path', 'label': 'Output Path', 'type': 'str', 'default': ''},
    ]

    def execute(self, inputs):
        node = inputs.get('volume_in')
        path = self.get_property('file_path')
        if node is None:
            raise ValueError("Save Volume: no input volume connected.")
        if not path:
            raise ValueError("Save Volume: no output path specified.")
        slicer.util.saveNode(node, path)
        return {}


# ---------------------------------------------------------------------------
# Shared routing helper
# ---------------------------------------------------------------------------

def _hide_all_volume_renderings():
    """Hide every volume rendering display node in the scene."""
    n = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLVolumeRenderingDisplayNode')
    for i in range(n):
        dn = slicer.mrmlScene.GetNthNodeByClass(i, 'vtkMRMLVolumeRenderingDisplayNode')
        if dn is not None:
            dn.SetVisibility(False)


def _scope_vr_to_volume(target_volume):
    """
    Make sure VR displays attached to OTHER volumes are hidden, while
    leaving the VR for `target_volume` (if any exists) visible.  This
    keeps the volume rendering for the volume we're currently viewing
    on, and only hides VRs for unrelated samples.
    """
    if target_volume is None:
        return
    target_id = target_volume.GetID()
    vr_logic  = slicer.modules.volumerendering.logic()

    n = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLScalarVolumeNode')
    for i in range(n):
        v = slicer.mrmlScene.GetNthNodeByClass(i, 'vtkMRMLScalarVolumeNode')
        if v is None:
            continue
        try:
            dn = vr_logic.GetFirstVolumeRenderingDisplayNode(v)
        except Exception:
            dn = None
        if dn is None:
            continue
        # Visible iff it belongs to the volume we're currently routing.
        # (We don't FORCE it visible — only ensure it's hidden when
        # unrelated.  The user's explicit ON/OFF state for the matching
        # volume's VR is preserved.)
        if v.GetID() != target_id:
            dn.SetVisibility(False)


def _route_volume_to_slices(node):
    """Show a volume in the conventional 3-slice + 3D layout.  Hides
    volume renderings for OTHER volumes so only displays related to
    `node` (its own VR, if any) remain visible."""
    _scope_vr_to_volume(node)

    lm = slicer.app.layoutManager()
    lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView)
    nid = node.GetID()
    for color in ('Red', 'Yellow', 'Green'):
        cn = slicer.mrmlScene.GetNodeByID(
            f'vtkMRMLSliceCompositeNode{color}')
        if cn:
            cn.SetBackgroundVolumeID(nid)
    slicer.util.resetSliceViews()


# ---------------------------------------------------------------------------
# Volumes — linked to Slicer's "Volumes" module (window/level, contrast, etc.)
# ---------------------------------------------------------------------------

class VolumesNode(LinkedModuleNode):
    """Display-property tweaks for a volume — opens Slicer's Volumes module."""

    NODE_NAME     = "Volumes"
    CATEGORY      = "I/O"
    LINKED_MODULE = "Volumes"

    INPUT_PORTS   = [("volume_in",  "Volume", VOLUME)]
    OUTPUT_PORTS  = [("volume_out", "Volume", VOLUME)]
    INPUT_SETTERS = {'volume_in': ('setMRMLVolumeNode', 'setMRMLNode')}

    def route_to_viewer(self):
        node = self._cache.get('volume_in')
        if node is not None:
            _route_volume_to_slices(node)


# ---------------------------------------------------------------------------
# Markups — linked to Slicer's "Markups" module (fiducials, lines, ROIs, ...)
# ---------------------------------------------------------------------------

class MarkupsNode(LinkedModuleNode):
    """Edit a markup node (fiducials, line, ROI, …) via the Markups module."""

    NODE_NAME     = "Markups"
    CATEGORY      = "I/O"
    LINKED_MODULE = "Markups"

    INPUT_PORTS   = [("markup_in",  "Markup", MARKUP)]
    OUTPUT_PORTS  = [("markup_out", "Markup", MARKUP)]
    INPUT_SETTERS = {'markup_in': ('setActiveMarkupsNode', 'setMRMLMarkupsNode',
                                    'setMRMLNode')}
