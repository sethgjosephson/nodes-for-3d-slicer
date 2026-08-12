"""
SlicerBaseNode, the pure-Python base class for all pipeline nodes.

NodeItem (QGraphicsObject) wraps this for canvas representation.
Subclasses declare ports and properties as class attributes, then
implement execute() and optionally route_to_viewer().

This module also exposes the graph-ownership helpers
(`_mark_ephemeral`, `_adopt_into_graph_folder`) used by every wrapper
that creates MRML nodes, so those nodes end up grouped in the
"Node Editor (auto)" Subject Hierarchy folder and are skipped on
.mrb save by default.
"""

# ---------------------------------------------------------------------------
# Debug logging: set SLICER_NODE_EDITOR_DEBUG=1 in the environment to see
# every swallowed exception and setter miss that is silent by default.
# ---------------------------------------------------------------------------

import os

_DEBUG = os.environ.get('SLICER_NODE_EDITOR_DEBUG', '') not in ('', '0')


def _debug(message):
    if _DEBUG:
        print(f"[NodeEditor:debug] {message}")


# ---------------------------------------------------------------------------
# Port data-type string constants
# ---------------------------------------------------------------------------
VOLUME        = "volume"
LABELMAP      = "labelmap"
SEGMENTATION  = "segmentation"
TRANSFORM     = "transform"
MODEL         = "model"
MARKUP        = "markup"
TABLE         = "table"
PLOT          = "plot"
TEXT          = "text"
COLOR         = "color"
SEQUENCE      = "sequence"   # reserved for Phase F (4D data)
ANY           = "any"


# ---------------------------------------------------------------------------
# Graph-ownership helpers: mark MRML nodes as graph-owned and group them
# under a Subject Hierarchy folder so they do not clutter the Data module.
# ---------------------------------------------------------------------------

NODE_EDITOR_FOLDER_NAME = "Node Editor (auto)"
NODE_EDITOR_FOLDER_ATTR = "NodeEditor.AutoFolder"


def _get_or_create_graph_folder():
    """
    Return the Subject Hierarchy item ID of the folder we park graph-owned
    nodes under, creating it on first use. Returns 0 if the SH node is
    unavailable (e.g. early in module load).
    """
    import slicer
    import vtk
    sh = slicer.mrmlScene.GetSubjectHierarchyNode()
    if sh is None:
        return 0
    scene_item = sh.GetSceneItemID()
    # Look for an existing folder marked with our attribute
    children = vtk.vtkIdList()
    try:
        sh.GetItemChildren(scene_item, children)
    except Exception:
        children = None
    if children is not None:
        for i in range(children.GetNumberOfIds()):
            cid = children.GetId(i)
            try:
                if sh.GetItemAttribute(cid, NODE_EDITOR_FOLDER_ATTR) == "1":
                    return cid
            except Exception:
                continue
    # Not found, create one
    try:
        folder_id = sh.CreateFolderItem(scene_item, NODE_EDITOR_FOLDER_NAME)
    except Exception:
        return 0
    if folder_id and folder_id != 0:
        try:
            sh.SetItemAttribute(folder_id, NODE_EDITOR_FOLDER_ATTR, "1")
        except Exception:
            pass
    return folder_id


def _adopt_into_graph_folder(mrml_node):
    """
    Reparent the given data node under the Node Editor (auto) folder in
    Subject Hierarchy. Safe to call on nodes that have no SH item yet
    (does nothing in that case).
    """
    if mrml_node is None:
        return
    import slicer
    sh = slicer.mrmlScene.GetSubjectHierarchyNode()
    if sh is None:
        return
    folder_id = _get_or_create_graph_folder()
    if not folder_id:
        return
    try:
        item_id = sh.GetItemByDataNode(mrml_node)
        if item_id and item_id != 0:
            sh.SetItemParent(item_id, folder_id)
    except Exception:
        pass


def _mark_ephemeral(mrml_node):
    """
    Mark a MRML node as graph-owned:
      1. SetSaveWithScene(False) on the data node and on every one of
         its storage and display child nodes, so .mrb saves do not
         accumulate stale intermediates.
      2. Reparent the node under the Node Editor (auto) folder for
         visual grouping in the Data module.

    NOTE: we deliberately do NOT call SetHideFromEditors(True). Graph
    nodes stay visible in the Data module and in node selectors;
    they're just neatly grouped under one folder. Use a stronger
    "hide entirely" helper later if a node should be fully internal
    (e.g. a transient parameter node).
    """
    if mrml_node is None:
        return

    def _flip_save(n):
        if n is None:
            return
        try:
            n.SetSaveWithScene(False)
        except Exception:
            pass

    _flip_save(mrml_node)
    # Storage nodes (volumes, models, segmentations carry these)
    try:
        for i in range(mrml_node.GetNumberOfStorageNodes()):
            _flip_save(mrml_node.GetNthStorageNode(i))
    except Exception:
        pass
    # Display nodes (vtkMRMLDisplayableNode subclasses)
    try:
        for i in range(mrml_node.GetNumberOfDisplayNodes()):
            _flip_save(mrml_node.GetNthDisplayNode(i))
    except Exception:
        pass

    _adopt_into_graph_folder(mrml_node)


class SlicerBaseNode:
    """
    Base for every node in the pipeline.

    Class attributes subclasses should override
    ─────────────────────────────────────────────
    NODE_NAME   : str   display name on the canvas
    CATEGORY    : str   groups the node in the Tab search menu
    NODE_COLOR  : (R,G,B)  overrides the category title-bar colour if set

    INPUT_PORTS / OUTPUT_PORTS
        list of (port_name: str, display_label: str, data_type: str)
        data_type should be one of the constants above (VOLUME, etc.)

    PROPERTIES
        list of dicts describing editable parameters:
        {
          'name':    str,           unique key
          'label':   str,           shown in properties panel
          'type':    'float'|'int'|'str'|'enum'|'bool',
          'default': value,
          # optional:
          'min': float,  'max': float,   # for float/int
          'items': [str, ...],            # for enum
        }
    """

    NODE_NAME    = "Base Node"
    CATEGORY     = "Utilities"
    NODE_COLOR   = None           # None → use CAT_COLOR[CATEGORY]

    # Stable identifier written into saved graphs. Defaults to the class
    # name; set explicitly if a class is ever renamed so old graph files
    # keep loading. Resolved through Nodes.NODE_TYPE_REGISTRY.
    NODE_TYPE    = None

    # True for nodes whose canonical content is hand-edited state
    # (Segment Editor strokes, markup placements). Their output cannot be
    # recomputed from upstream, so when an upstream input changes the node
    # shows a stale-input warning badge instead of silently re-cooking.
    EDIT_STATE   = False

    INPUT_PORTS  = []
    OUTPUT_PORTS = []
    PROPERTIES   = []

    # Optional: name of a Slicer module whose widget should be shown in the
    # left panel when this node is selected (e.g. 'VolumeRendering',
    # 'SegmentEditor').  When set, Slicer auto-switches to that module
    # and `configure_module_widget` is called to point it at this node's
    # data.  When None (default), the standard PROPERTIES form is built
    # in the Node Editor's own properties panel.
    LINKED_MODULE = None

    # If True (default), this node participates in the "auto-rerun on
    # property change" loop: editing any node's parameter schedules a
    # debounced re-execution of whichever node is currently in the active
    # viewer slot, walking back through dirty ancestors as usual.
    # Set False on expensive operations (long-running CLI, file load,
    # interactive editing) — they still re-run when the user presses 1
    # explicitly, but the auto loop will refuse to fire if it would
    # require running them.
    AUTO_EXECUTE = True

    # ------------------------------------------------------------------

    def __init__(self):
        self._props     = {p['name']: p['default'] for p in self.PROPERTIES}
        # _cache: what DOWNSTREAM sees on each port. Mirrors execute()'s
        # return AND gets overwritten by passthrough when this node is
        # disabled (so downstream reads upstream's value).
        self._cache     = {}
        # _owned_outputs: MRML nodes THIS node personally created and is
        # responsible for. Passthrough does NOT touch this. Reused on
        # subsequent execute() calls so each node keeps writing back to
        # the same MRML node instead of polluting an upstream input.
        self._owned_outputs = {}
        self.is_dirty   = True    # True → needs re-execution
        self.is_disabled = False  # compositor-style D-key: skip execute(), passthrough

        # Set to the exception text when the last execute() raised; the
        # canvas paints a red error badge while this is non-None. Cleared
        # at the start of every run.
        self._last_error = None

        # EDIT_STATE nodes only: True when an upstream input changed under
        # hand-edited content, so that content may be misaligned with its
        # source. Cleared when the user double-clicks the node (opening
        # its editor counts as acknowledging the warning).
        self.stale_input = False

        # MRML ModifiedEvent observers on the node's CURRENT input MRML
        # nodes.  Maintained by _refresh_input_observers() which the
        # executor calls right after resolving inputs.  Keyed by input
        # port name; value is (mrml_node, observer_tag).
        self._input_observers = {}

        # Reentrance flag: set True while our own execute() runs, so any
        # ModifiedEvent fired by our own activity (e.g. writing to an
        # output node that's also an upstream-shared MRML node) doesn't
        # bounce back through our observer and falsely mark us dirty.
        self._self_modified = False

        # Debounce flag: True while a dirty-mark is already pending via
        # QTimer.singleShot, so a burst of ModifiedEvents only fires one
        # dirty propagation.
        self._dirty_pending = False

    # ------------------------------------------------------------------
    # Property access
    # ------------------------------------------------------------------

    def get_property(self, name):
        return self._props.get(name)

    def set_property(self, name, value):
        """Update a parameter value.  Caller is responsible for dirty propagation."""
        self._props[name] = value
        self.is_dirty = True

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    def execute(self, inputs: dict) -> dict:
        """
        Run the Slicer operation.

        Parameters
        ----------
        inputs : dict
            {port_name: vtkMRMLNode | None}  — upstream outputs keyed by
            this node's input port name.

        Returns
        -------
        dict
            {port_name: vtkMRMLNode}  — outputs, one entry per OUTPUT_PORT.
            The Executor stores these into self._cache automatically.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute(inputs)")

    # ------------------------------------------------------------------
    # Viewer routing  (override in concrete nodes)
    # ------------------------------------------------------------------

    def route_to_viewer(self):
        """
        Apply this node's cached output to Slicer's viewer.
        Default is a no-op; subclasses override to change layout/routing.
        """
        pass

    def route_fullscreen(self):
        """
        Apply this node's cached output to Slicer's viewer in a
        single-pane fullscreen layout, hiding the auxiliary views.

        Default implementation: walk our OUTPUT_PORTS, find a volume- or
        labelmap-typed one, and route it to the single red slice view
        via _route_volume_fullscreen. Override when the node's output
        is best shown another way (e.g. VolumeRendering uses pure 3D).

        Falls back to route_to_viewer when no volume output is available.
        """
        for port_name, _label, dtype in self.OUTPUT_PORTS:
            if dtype in ('volume', 'labelmap'):
                vol = self._cache.get(port_name)
                if vol is not None:
                    try:
                        from .io_nodes import _route_volume_fullscreen
                        _route_volume_fullscreen(vol)
                        return
                    except Exception:
                        break
        # No suitable volume output; fall back to the normal route
        self.route_to_viewer()

    # ------------------------------------------------------------------
    # Custom properties widget (optional)
    # ------------------------------------------------------------------

    def build_properties_widget(self, parent, node_item):
        """
        Optional hook: return a fully-built QWidget to embed in the
        properties panel.  Return None (default) to fall back to the
        auto-generated PROPERTIES form.

        Most nodes should use LINKED_MODULE instead — set that to the
        name of a Slicer module and Slicer's own widget for that module
        will be shown in the left panel.  This hook is for nodes that
        want a fully bespoke widget.
        """
        return None

    def configure_module_widget(self, module_widget, node_item):
        """
        Called after Slicer switches to LINKED_MODULE.  Override to
        point the module widget at this node's data — typically by
        calling its `setMRMLVolumeNode(...)` / `setSegmentationNode(...)`
        / similar setter with the value cached on this node.
        """
        pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_cached_output(self, port_name):
        return self._cache.get(port_name)

    def _get_or_create_output(self, port_name, name_hint):
        """
        Return the MRML node this node owns for port_name, creating it
        on first use. Read from _owned_outputs (NOT _cache) so that
        passthrough — which writes upstream refs into _cache while a
        node is disabled — never tricks us into mutating an upstream
        input's MRML data on the next enabled execute().
        """
        import slicer
        existing = self._owned_outputs.get(port_name)
        if existing and slicer.mrmlScene.GetNodeByID(existing.GetID()):
            return existing
        new_node = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
        new_node.SetName(name_hint)
        new_node.CreateDefaultDisplayNodes()
        _mark_ephemeral(new_node)
        self._owned_outputs[port_name] = new_node
        return new_node

    def mark_dirty(self):
        self.is_dirty = True

    def mark_clean(self):
        self.is_dirty = False

    # ------------------------------------------------------------------
    # Async completion (call from a CLI completion observer)
    # ------------------------------------------------------------------

    def _notify_async_complete(self, success=True, error_message=None):
        """
        Call from an async node's completion callback once its CLI has
        finished writing real data into the placeholder outputs.

        On success: marks this node clean, marks everything downstream
        dirty (the executor blocked descendants while we were pending, so
        they never saw the placeholder data), repaints, and re-cooks the
        active viewer slot if this node feeds it.

        On failure: records the error for the canvas badge and leaves the
        node dirty so the next press-1 retries.
        """
        self._async_pending = False
        node_item = getattr(self, '_executing_node_item', None)

        if not success:
            self._last_error = error_message or "asynchronous run failed"
            if node_item is not None:
                try:
                    node_item.update()
                except Exception:
                    pass
            return

        self._last_error = None
        self.mark_clean()
        if node_item is None:
            return
        try:
            node_item.update()
        except Exception:
            pass

        scene = node_item.scene()
        if scene is None or not hasattr(scene, 'get_outgoing_edges'):
            return

        # Downstream-only dirty walk (mark_dirty_from would re-dirty us).
        downstream = set()
        for edge in scene.get_outgoing_edges(node_item):
            target = edge.target_port.node_item
            scene.mark_dirty_from(target)
            stack = [target]
            while stack:
                current = stack.pop()
                if current in downstream:
                    continue
                downstream.add(current)
                for e in scene.get_outgoing_edges(current):
                    stack.append(e.target_port.node_item)

        # If the active viewer slot shows us or a descendant, re-cook it
        # now so the user's view updates without another keypress.
        router = getattr(scene, '_router_ref', None)
        if router is None:
            return
        try:
            active = router.get_active_slot()
            slot_node = router.get_slot_node(active)
            if slot_node is node_item or slot_node in downstream:
                router.activate(active)
        except Exception as exc:
            _debug(f"{self.NODE_NAME}: post-async viewer refresh "
                   f"failed: {exc}")

    # ------------------------------------------------------------------
    # MRML observers — auto-dirty when upstream MRML changes externally
    # ------------------------------------------------------------------

    def _refresh_input_observers(self, node_item):
        """
        Rebind ModifiedEvent observers on the MRML nodes currently feeding
        this node's inputs.  Called by the executor after it resolves
        inputs for a given _run_node call, so observers always reflect
        the actual current graph topology and upstream cache state.

        When any of those upstream MRML nodes is later modified by any
        source (user edit in another module, a script, another graph
        node), our callback marks this node dirty and propagates dirty
        downstream.  Debounced via QTimer (B.2) so a burst of
        ModifiedEvents only triggers one dirty pass.

        Skipped silently if we have no scene reference yet.
        """
        self._clear_input_observers()
        if node_item is None:
            return
        scene = node_item.scene()
        if scene is None or not hasattr(scene, 'get_incoming_edge'):
            return

        import vtk
        for port_name, _label, _dtype in self.INPUT_PORTS:
            in_port = node_item.get_port(port_name, is_input=True)
            if in_port is None:
                continue
            edge = scene.get_incoming_edge(in_port)
            if edge is None or edge.source_port is None:
                continue
            up_node_data = edge.source_port.node_item.node_data
            mrml_node = up_node_data._cache.get(edge.source_port.port_name)
            if mrml_node is None:
                continue
            try:
                tag = mrml_node.AddObserver(
                    vtk.vtkCommand.ModifiedEvent,
                    lambda caller, event, ni=node_item, up=up_node_data:
                        self._on_input_modified(ni, up))
                self._input_observers[port_name] = (mrml_node, tag)
            except Exception as exc:
                _debug(f"{self.NODE_NAME}: could not observe input "
                       f"'{port_name}': {exc}")
                continue

    def _clear_input_observers(self):
        """Remove every input observer we currently hold."""
        for port_name, (mrml_node, tag) in list(self._input_observers.items()):
            try:
                mrml_node.RemoveObserver(tag)
            except Exception:
                pass
        self._input_observers.clear()

    def _on_input_modified(self, node_item, up_node_data=None):
        """
        Observer callback (debounced).  An upstream MRML node fired a
        ModifiedEvent.  Mark this graph node and everything downstream
        dirty, and repaint to show the dirty indicator.

        Suppressed when self._self_modified is set (we're inside our own
        execute() and the Modified event is a side-effect of our own
        write) AND when the upstream graph node is inside ITS execute():
        that write is graph-internal, the executor already runs us in the
        same pass, and scheduling a dirty mark here would land after the
        pass and falsely re-dirty a freshly-cleaned chain. External edits
        (other modules, scripts, the user) are still detected because
        they happen outside any execute() window.
        """
        if self._self_modified:
            return
        if up_node_data is not None and getattr(up_node_data,
                                                '_self_modified', False):
            return
        if self._dirty_pending:
            return
        self._dirty_pending = True

        def _fire():
            self._dirty_pending = False
            self.mark_dirty()
            # Hand-edited content cannot be re-cooked from upstream; flag
            # that it may now be misaligned with its changed input.
            if self.EDIT_STATE:
                self.stale_input = True
            # This fires 100 ms after scheduling; the canvas item or its
            # scene may have been deleted in between (module reload,
            # graph clear, test teardown). A call into a dead PythonQt
            # wrapper can hard-crash Slicer, so guard the entire block.
            try:
                scene = node_item.scene() if node_item is not None else None
                if scene is not None and hasattr(scene, 'mark_dirty_from'):
                    scene.mark_dirty_from(node_item)
                elif node_item is not None:
                    node_item.update()
            except Exception:
                pass

        try:
            import qt
            qt.QTimer.singleShot(100, _fire)
        except Exception:
            # No Qt event loop available — fire synchronously
            _fire()

    def __repr__(self):
        return f"<{self.__class__.__name__} dirty={self.is_dirty}>"


# ---------------------------------------------------------------------------
# LinkedModuleNode — thin wrapper around an existing Slicer module
# ---------------------------------------------------------------------------

class LinkedModuleNode(SlicerBaseNode):
    """
    Base class for nodes that are *thin wrappers* around an existing
    Slicer module.  When the user double-clicks the node, Slicer
    switches to LINKED_MODULE and the module's native widget shows up
    in the left panel — pre-configured to point at this node's data.

    Subclasses typically only need to set:
      - LINKED_MODULE  : str    (the Slicer module name)
      - INPUT_PORTS    : list   (typed ports for the data flow)
      - OUTPUT_PORTS   : list   (often a passthrough — same MRML node out)
      - INPUT_SETTERS  : dict   ({port_name: 'setterMethodName'} mapping
                                  how each input is pushed to the module
                                  widget).  Multiple candidate setter
                                  names may be supplied as a tuple.

    `execute(inputs)` defaults to passthrough (each input becomes the
    same-named output) so the data just flows through untouched —
    visualization tweaks happen inside the linked module's widget.
    Override execute() if the node actually transforms data.
    """

    LINKED_MODULE = None
    INPUT_SETTERS = {}      # {port_name: 'setterName'} or {port_name: ('setA', 'setB')}

    # ------------------------------------------------------------------

    def configure_module_widget(self, module_widget, node_item):
        """Push each input port's value to the module widget's setter."""
        for port_name, setter_spec in self.INPUT_SETTERS.items():
            value = self._resolve_input(node_item, port_name)
            if value is None:
                continue
            setters = (setter_spec,) if isinstance(setter_spec, str) else tuple(setter_spec)
            pushed = False
            for setter_name in setters:
                if hasattr(module_widget, setter_name):
                    try:
                        getattr(module_widget, setter_name)(value)
                        pushed = True
                        break
                    except Exception as exc:
                        _debug(f"{self.NODE_NAME}: setter "
                               f"'{setter_name}' raised: {exc}")
                        continue
            if not pushed:
                _debug(f"{self.NODE_NAME}: no working setter for input "
                       f"'{port_name}' (tried {', '.join(setters)}); the "
                       f"{self.LINKED_MODULE} widget API may have changed")

    def _resolve_input(self, node_item, port_name):
        """Walk upstream to fetch the current value at our `port_name` input."""
        if node_item is None:
            return self._cache.get(port_name)
        scene = node_item.scene()
        if scene is None or not hasattr(scene, 'get_incoming_edge'):
            return self._cache.get(port_name)
        in_port = node_item.get_port(port_name, is_input=True)
        if in_port is None:
            return self._cache.get(port_name)
        edge = scene.get_incoming_edge(in_port)
        if edge is None or edge.source_port is None:
            return self._cache.get(port_name)
        up = edge.source_port.node_item.node_data
        return up._cache.get(edge.source_port.port_name)

    # Default execute: pure passthrough.  Each input maps to a same-named
    # output if both ports exist.  Override for nodes that transform data.
    def execute(self, inputs):
        result = {}
        out_names = {p[0] for p in self.OUTPUT_PORTS}
        for in_name, value in inputs.items():
            if value is None:
                continue
            self._cache[in_name] = value
            if in_name in out_names:
                result[in_name] = value
            else:
                # Match the first output port if naming differs
                if self.OUTPUT_PORTS and len(self.OUTPUT_PORTS) == 1:
                    result[self.OUTPUT_PORTS[0][0]] = value
        return result
