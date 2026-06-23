"""
NodeEditorScene — QGraphicsScene managing nodes, edges, and the
edge-drag state machine.

Topology queries used by Executor live here so neither NodeItem nor
Executor needs to know about the full graph.
"""

from ._qt import (QGraphicsScene, QPointF, Qt, Signal,
                   QColor, QPainter, QBrush, QPen, QPixmap, QTransform)

from .node_item  import NodeItem
from .edge_item  import EdgeItem
from .port_item  import PortItem
from .constants  import (CANVAS_BG, GRID_DOT_COLOR, GRID_SPACING,
                          NODE_WIDTH, NODE_TITLE_HEIGHT, NODE_BODY_HEIGHT)


def _node_position(node_item):
    """
    Return the QPointF position of a NodeItem, regardless of whether
    PythonQt exposes `pos` as a property or a method.
    """
    p = node_item.pos
    if callable(p):
        try:
            p = p()
        except Exception:
            return QPointF(0.0, 0.0)
    return p


class NodeEditorScene(QGraphicsScene):
    """
    Central scene.  Owns the list of edges and drives the edge-drag
    state machine.

    Signals
    -------
    node_selected(NodeItem | None)
        Emitted when the canvas selection changes.
    """

    node_selected = Signal(object)   # kept for API compatibility

    def __init__(self, parent=None):
        super().__init__(parent)

        self._edges            = []          # [EdgeItem]
        self._node_items       = []          # [NodeItem] — kept because PythonQt
                                             # loses subclass identity when items
                                             # round-trip through QGraphicsScene
        self._drag_edge        = None        # temp EdgeItem during drag
        self._drag_source_port = None        # PortItem where drag started
        self._selection_listener = None      # plain Python callback (reliable)
        self._property_change_listener = None  # canvas auto-rerun hook
        self._mutation_listener = None       # widget hook for .mrb parameter-node sync
        self._drop_highlight_edge = None     # edge currently highlighted for splice

        # Undo/redo state (snapshot-based)
        self._undo_stack = []
        self._redo_stack = []
        self._undo_limit = 50
        self._suppress_undo_capture = False
        self._router_ref = None              # set externally for restore-time slot rebind

        self.setBackgroundBrush(QBrush(QColor(*CANVAS_BG)))
        self._dot_pixmap = self._build_dot_tile()

        # Pre-set a large scene rect so the grid fills the viewport
        self.setSceneRect(-4000, -4000, 8000, 8000)

    # ------------------------------------------------------------------
    # Background grid
    # ------------------------------------------------------------------

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QBrush(QColor(*CANVAS_BG)))
        painter.setRenderHint(QPainter.Antialiasing, False)

        dot_color = QColor(*GRID_DOT_COLOR)
        painter.setPen(QPen(dot_color, 1.5))

        left   = int(rect.left())   - (int(rect.left())   % GRID_SPACING)
        top    = int(rect.top())    - (int(rect.top())    % GRID_SPACING)
        right  = int(rect.right())  + GRID_SPACING
        bottom = int(rect.bottom()) + GRID_SPACING

        x = left
        while x <= right:
            y = top
            while y <= bottom:
                painter.drawPoint(x, y)
                y += GRID_SPACING
            x += GRID_SPACING

    @staticmethod
    def _build_dot_tile():
        """Pre-rendered tile (unused; kept for future GPU-path option)."""
        return None

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def add_node(self, node_data, scene_pos=None):
        """Create a NodeItem from a SlicerBaseNode instance and add it."""
        item = NodeItem(node_data, scene_pos)
        self.addItem(item)
        self._node_items.append(item)
        return item

    def set_selection_listener(self, callback):
        """Register a plain Python callback for node-selection events."""
        self._selection_listener = callback

    def set_property_change_listener(self, callback):
        """Register a callback fired when any node's property changes,
        so the canvas can schedule a debounced auto-rerun."""
        self._property_change_listener = callback

    def notify_property_changed(self, node_item):
        """Called by NodeItem.set_property after dirty-propagation."""
        if self._property_change_listener is not None:
            try:
                self._property_change_listener(node_item)
            except Exception:
                import traceback; traceback.print_exc()
        self.notify_mutation()

    def set_mutation_listener(self, callback):
        """Register a callback fired whenever the graph changes
        structurally OR a property is edited.  Used by the widget to
        keep the .mrb parameter-node copy of the graph in sync."""
        self._mutation_listener = callback

    def notify_mutation(self):
        """Fire the mutation listener.  Called internally by capture_undo
        and notify_property_changed; also callable directly by external
        code that modifies the graph in ways those paths don't cover
        (e.g. _clear_graph from the widget)."""
        if self._mutation_listener is not None:
            try:
                self._mutation_listener()
            except Exception:
                import traceback; traceback.print_exc()

    def notify_node_selected(self, node_item):
        """Called by NodeItem.mousePressEvent (direct call, not signal)."""
        if self._selection_listener is not None:
            try:
                self._selection_listener(node_item)
            except Exception:
                import traceback; traceback.print_exc()
        try:
            self.node_selected.emit(node_item)
        except Exception:
            pass

    def remove_node(self, node_item):
        """Remove node and all its connected edges."""
        # Drop any MRML observers this node holds before its references go
        # away, so we don't leak observer tags on lingering MRML nodes.
        try:
            node_item.node_data._clear_input_observers()
        except Exception:
            pass
        for edge in self.edges_of(node_item):
            self.remove_edge(edge)
        self.removeItem(node_item)
        if node_item in self._node_items:
            self._node_items.remove(node_item)

    def on_node_moved(self, node_item):
        """Called by NodeItem.itemChange; refreshes attached edges."""
        for edge in self.edges_of(node_item):
            edge.update_path()

    # ------------------------------------------------------------------
    # Edge management
    # ------------------------------------------------------------------

    def connect_ports(self, source_port, target_port):
        """
        Validate and create a permanent edge.  Rules:
          - source must be an output port, target an input port
          - target port may not already have an incoming edge
          - no self-loops
        """
        if source_port.is_input or not target_port.is_input:
            return None
        if source_port.node_item is target_port.node_item:
            return None
        # Remove existing edge into target (input ports are 1:1)
        existing = self.get_incoming_edge(target_port)
        if existing:
            self.remove_edge(existing)

        edge = EdgeItem(source_port, target_port)
        self._edges.append(edge)
        self.addItem(edge)
        edge.update_path()

        # Downstream of target node is now dirty
        self.mark_dirty_from(target_port.node_item)
        return edge

    def remove_edge(self, edge):
        if edge in self._edges:
            self._edges.remove(edge)
        self.removeItem(edge)
        # Target node no longer has upstream data → dirty
        if edge.target_port:
            self.mark_dirty_from(edge.target_port.node_item)

    # ------------------------------------------------------------------
    # Edge-drag state machine
    # ------------------------------------------------------------------

    def start_edge_drag(self, port_item):
        self._drag_source_port = port_item
        self._drag_edge        = EdgeItem(port_item, None)
        self.addItem(self._drag_edge)

    def mouseMoveEvent(self, event):
        if self._drag_edge is not None:
            self._drag_edge.set_float_end(event.scenePos())
        QGraphicsScene.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        if self._drag_edge is not None and event.button() == Qt.LeftButton:
            # Find port under cursor (exclude the drag source)
            target = self._port_at(event.scenePos(),
                                   exclude=self._drag_source_port)
            if target is not None:
                self.capture_undo()
                self.connect_ports(self._drag_source_port, target)

            self.removeItem(self._drag_edge)
            self._drag_edge        = None
            self._drag_source_port = None
            event.accept()
            return

        QGraphicsScene.mouseReleaseEvent(self, event)

    # ------------------------------------------------------------------
    # Dirty propagation
    # ------------------------------------------------------------------

    def mark_dirty_from(self, start_node_item):
        """BFS downstream from start_node_item, marking all nodes dirty."""
        visited = set()
        queue   = [start_node_item]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            current.node_data.mark_dirty()
            current.update()
            for edge in self.get_outgoing_edges(current):
                queue.append(edge.target_port.node_item)

    # ------------------------------------------------------------------
    # Topology queries  (used by Executor)
    # ------------------------------------------------------------------

    def all_node_items(self):
        return list(self._node_items)

    def selected_node_items(self):
        """NodeItems currently selected (PythonQt-safe)."""
        result = []
        for ni in self._node_items:
            try:
                sel = ni.isSelected()
            except Exception:
                sel = bool(getattr(ni, 'selected', False))
            if sel:
                result.append(ni)
        return result

    def edges_of(self, node_item):
        return [e for e in self._edges
                if (e.source_port and e.source_port.node_item is node_item)
                or (e.target_port and e.target_port.node_item is node_item)]

    def get_incoming_edges(self, node_item):
        return [e for e in self._edges
                if e.target_port and e.target_port.node_item is node_item]

    def get_outgoing_edges(self, node_item):
        return [e for e in self._edges
                if e.source_port and e.source_port.node_item is node_item]

    def get_incoming_edge(self, port_item):
        """Return the single edge feeding into an input port, or None."""
        for edge in self._edges:
            if edge.target_port is port_item:
                return edge
        return None

    # ------------------------------------------------------------------
    # QoL helpers: shake-to-disconnect, auto-connect, drop-on-pipe
    # ------------------------------------------------------------------

    def build_splice_out_plan(self, node_item):
        """
        Compute pairs of (upstream_output_port, downstream_input_port)
        that should be connected after `node_item` is removed, so that
        a node in the middle of a pipe leaves the rest of the pipeline
        intact.  Pairs each incoming edge with a type-compatible outgoing
        edge.  Doesn't modify the graph — caller decides what to do.
        """
        incoming = [e for e in self._edges
                    if e.target_port and e.target_port.node_item is node_item]
        outgoing = [e for e in self._edges
                    if e.source_port and e.source_port.node_item is node_item]

        plan = []
        used_out = set()
        for in_edge in incoming:
            for out_edge in outgoing:
                if id(out_edge) in used_out:
                    continue
                up   = in_edge.source_port
                down = out_edge.target_port
                if up is None or down is None:
                    continue
                if (up.data_type == down.data_type
                        or up.data_type == 'any'
                        or down.data_type == 'any'):
                    plan.append((up, down))
                    used_out.add(id(out_edge))
                    break
        return plan

    def disconnect_all_edges(self, node_item):
        """
        Remove every edge connected to this node.  If the node sits in
        the middle of a pipe (has both incoming AND outgoing edges with
        compatible types), splice it OUT — directly connect upstream
        to downstream so the rest of the pipeline stays intact.
        """
        if not self.edges_of(node_item):
            return
        self.capture_undo()

        plan = self.build_splice_out_plan(node_item)

        # Remove every edge of this node
        for edge in list(self.edges_of(node_item)):
            self.remove_edge(edge)

        # Reconnect the spliced pairs
        for up, down in plan:
            self.connect_ports(up, down)

    def _find_compatible_pair(self, src_outputs, dst_inputs):
        """Return (out_port, in_port) of the first type-compatible match."""
        for op in src_outputs:
            for ip in dst_inputs:
                if (op.data_type == ip.data_type
                        or op.data_type == 'any'
                        or ip.data_type == 'any'):
                    return op, ip
        return None, None

    def try_auto_connect(self, source_node, new_node):
        """
        Wire `new_node` after `source_node`.  If source_node already had
        outgoing edges and new_node has a compatible output, splice
        new_node into the pipe (source → new → old downstream).
        """
        if source_node is None or new_node is None or source_node is new_node:
            return False

        src_out, new_in = self._find_compatible_pair(
            list(source_node._output_ports.values()),
            list(new_node._input_ports.values()))
        if src_out is None or new_in is None:
            return False

        # Find any existing downstream connections to splice through
        existing = [e for e in self._edges if e.source_port is src_out]
        new_outputs = list(new_node._output_ports.values())

        if existing and new_outputs:
            # Pick a new-node output that's compatible with the first downstream
            for op in new_outputs:
                splice_target = None
                for e in existing:
                    if (op.data_type == e.target_port.data_type
                            or op.data_type == 'any'
                            or e.target_port.data_type == 'any'):
                        splice_target = e.target_port
                        break
                if splice_target is not None:
                    new_out = op
                    # Reroute every existing edge through new_node
                    for e in list(existing):
                        old_target = e.target_port
                        self.remove_edge(e)
                        self.connect_ports(new_out, old_target)
                    break

        # Finally connect source → new
        self.connect_ports(src_out, new_in)
        return True

    def _find_splice_edge(self, node_item):
        """Return (edge, in_port, out_port) for a viable splice, or None."""
        # Skip if node already has any edges
        if any(e for e in self._edges
               if (e.source_port and e.source_port.node_item is node_item)
               or (e.target_port and e.target_port.node_item is node_item)):
            return None

        inputs  = list(node_item._input_ports.values())
        outputs = list(node_item._output_ports.values())
        if not inputs or not outputs:
            return None

        bbox = node_item.sceneBoundingRect()

        for edge in self._edges:
            if edge.source_port is None or edge.target_port is None:
                continue
            path = edge.path()
            hit = False
            for k in range(1, 20):
                if bbox.contains(path.pointAtPercent(k / 20.0)):
                    hit = True
                    break
            if not hit:
                continue

            up_type   = edge.source_port.data_type
            down_type = edge.target_port.data_type
            in_port = next((p for p in inputs
                            if p.data_type == up_type
                            or p.data_type == 'any'
                            or up_type == 'any'), None)
            out_port = next((p for p in outputs
                             if p.data_type == down_type
                             or p.data_type == 'any'
                             or down_type == 'any'), None)
            if in_port is not None and out_port is not None:
                return edge, in_port, out_port
        return None

    def update_drop_highlight(self, node_item):
        """While `node_item` is being dragged, highlight the edge it
        would splice into if released right now."""
        candidate = self._find_splice_edge(node_item)
        new_edge  = candidate[0] if candidate else None
        if new_edge is self._drop_highlight_edge:
            return
        if self._drop_highlight_edge is not None:
            try:
                self._drop_highlight_edge.set_drop_highlight(False)
            except Exception:
                pass
        self._drop_highlight_edge = new_edge
        if new_edge is not None:
            new_edge.set_drop_highlight(True)

    def clear_drop_highlight(self):
        if self._drop_highlight_edge is not None:
            try:
                self._drop_highlight_edge.set_drop_highlight(False)
            except Exception:
                pass
            self._drop_highlight_edge = None

    def try_insert_into_pipe(self, node_item):
        """If `node_item` was dropped on a pipe, splice it in."""
        self.clear_drop_highlight()
        match = self._find_splice_edge(node_item)
        if match is None:
            return False
        self.capture_undo()
        edge, in_port, out_port = match
        upstream_port   = edge.source_port
        downstream_port = edge.target_port
        self.remove_edge(edge)
        self.connect_ports(upstream_port, in_port)
        self.connect_ports(out_port, downstream_port)
        return True

    # ------------------------------------------------------------------
    # Undo / Redo  (snapshot-based — captures the entire serialised graph)
    # ------------------------------------------------------------------

    def set_router(self, router):
        self._router_ref = router

    def capture_undo(self):
        """Snapshot the current graph state for undo.  Called by user-action
        entry points BEFORE making structural changes."""
        if self._suppress_undo_capture:
            return
        try:
            snap = self.serialise()
        except Exception:
            import traceback; traceback.print_exc()
            return
        # Skip if identical to the previous snapshot — avoids duplicate
        # entries when several capture points fire for the same logical action.
        if self._undo_stack and self._undo_stack[-1] == snap:
            return
        self._undo_stack.append(snap)
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        # Any captured-for-undo change is by definition a graph mutation
        self.notify_mutation()

    def undo(self):
        if not self._undo_stack:
            return False
        try:
            current = self.serialise()
        except Exception:
            current = None
        state = self._undo_stack.pop()
        if current is not None:
            self._redo_stack.append(current)
        self._restore_state(state)
        return True

    def redo(self):
        if not self._redo_stack:
            return False
        try:
            current = self.serialise()
        except Exception:
            current = None
        state = self._redo_stack.pop()
        if current is not None:
            self._undo_stack.append(current)
        self._restore_state(state)
        return True

    def _restore_state(self, state):
        """Wipe and reload from a serialised snapshot."""
        self._suppress_undo_capture = True
        try:
            # Reset router slots — referenced NodeItems will be recreated
            if self._router_ref is not None:
                try:
                    self._router_ref._slots = {i: None for i in range(1, 11)}
                except Exception:
                    pass
            self.deserialise(state, self._router_ref)
        finally:
            self._suppress_undo_capture = False

    # ------------------------------------------------------------------
    # Copy / Paste  (returns/consumes plain dicts so callers can stash)
    # ------------------------------------------------------------------

    def copy_selection(self):
        """Return a clipboard dict for the currently-selected nodes (and
        any edges fully contained within the selection).  None if empty."""
        selected = self.selected_node_items()
        if not selected:
            return None

        sel_ids = {id(ni) for ni in selected}
        idx_map = {}
        nodes_data = []
        for i, ni in enumerate(selected):
            idx_map[id(ni)] = i
            p = _node_position(ni)
            nodes_data.append({
                'id':       i,
                'class':    ni.node_data.__class__.__name__,
                'module':   ni.node_data.__class__.__module__,
                'x':        p.x(),
                'y':        p.y(),
                'props':    dict(ni.node_data._props),
                'disabled': bool(getattr(ni.node_data, 'is_disabled', False)),
            })

        edges_data = []
        for edge in self._edges:
            if edge.source_port is None or edge.target_port is None:
                continue
            sid = id(edge.source_port.node_item)
            tid = id(edge.target_port.node_item)
            if sid in sel_ids and tid in sel_ids:
                edges_data.append({
                    'src_node': idx_map[sid],
                    'src_port': edge.source_port.port_name,
                    'dst_node': idx_map[tid],
                    'dst_port': edge.target_port.port_name,
                })

        return {'nodes': nodes_data, 'edges': edges_data}

    def paste_clipboard(self, clipboard, scene_pos=None):
        """Paste a clipboard dict, optionally re-centred at scene_pos."""
        if not clipboard or not clipboard.get('nodes'):
            return []

        import importlib
        nodes = clipboard['nodes']

        # Compute offset
        if scene_pos is not None:
            cx = sum(n['x'] for n in nodes) / len(nodes)
            cy = sum(n['y'] for n in nodes) / len(nodes)
            ox, oy = scene_pos.x() - cx, scene_pos.y() - cy
        else:
            ox, oy = 30.0, 30.0

        self.clearSelection()
        new_items = {}
        for nd in nodes:
            try:
                mod = importlib.import_module(nd['module'])
                cls = getattr(mod, nd['class'])
            except Exception:
                continue
            try:
                inst = cls()
            except Exception:
                continue
            for k, v in nd.get('props', {}).items():
                inst.set_property(k, v)
            ni = self.add_node(inst, QPointF(nd['x'] + ox, nd['y'] + oy))
            if nd.get('disabled'):
                ni.node_data.is_disabled = True
                ni.update()
            ni.setSelected(True)
            new_items[nd['id']] = ni

        for ed in clipboard.get('edges', []):
            sni = new_items.get(ed['src_node'])
            dni = new_items.get(ed['dst_node'])
            if sni is None or dni is None:
                continue
            sport = sni.get_port(ed['src_port'], is_input=False)
            dport = dni.get_port(ed['dst_port'], is_input=True)
            if sport and dport:
                self.connect_ports(sport, dport)

        return list(new_items.values())

    # ------------------------------------------------------------------
    # Selection handling
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        # Click on empty space → deselect (but keep the properties panel
        # showing whatever was last double-clicked, so dragging around
        # doesn't keep wiping the user's context).
        item = self.itemAt(event.scenePos(),
                           self.views()[0].transform() if self.views() else QTransform())
        if item is None:
            self.clearSelection()
        QGraphicsScene.mousePressEvent(self, event)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def serialise(self):
        """Return a JSON-serialisable dict describing the full graph."""
        import json

        nodes = []
        node_ids = {}
        for i, ni in enumerate(self.all_node_items()):
            node_ids[id(ni)] = i
            p = _node_position(ni)
            nodes.append({
                'id':       i,
                'class':    ni.node_data.__class__.__name__,
                'module':   ni.node_data.__class__.__module__,
                'x':        p.x(),
                'y':        p.y(),
                'props':    dict(ni.node_data._props),
                'slot':     ni._viewer_slot,
                'disabled': bool(getattr(ni.node_data, 'is_disabled', False)),
            })

        edges = []
        for edge in self._edges:
            if edge.source_port and edge.target_port:
                edges.append({
                    'src_node':  node_ids[id(edge.source_port.node_item)],
                    'src_port':  edge.source_port.port_name,
                    'dst_node':  node_ids[id(edge.target_port.node_item)],
                    'dst_port':  edge.target_port.port_name,
                })

        return {'nodes': nodes, 'edges': edges}

    def deserialise(self, data, router=None):
        """Restore a graph from a serialised dict."""
        import importlib

        # Clear existing content
        for ni in self.all_node_items():
            self.remove_node(ni)

        index = {}    # serialised id → NodeItem
        for nd in data.get('nodes', []):
            mod   = importlib.import_module(nd['module'])
            cls   = getattr(mod, nd['class'])
            node  = cls()
            for k, v in nd.get('props', {}).items():
                node.set_property(k, v)
            ni    = self.add_node(node, QPointF(nd['x'], nd['y']))
            if nd.get('disabled'):
                ni.node_data.is_disabled = True
                ni.update()
            if nd.get('slot') and router:
                router._slots[nd['slot']] = ni
                ni.set_viewer_slot(nd['slot'])
            index[nd['id']] = ni

        for ed in data.get('edges', []):
            src_ni   = index[ed['src_node']]
            dst_ni   = index[ed['dst_node']]
            src_port = src_ni.get_port(ed['src_port'], is_input=False)
            dst_port = dst_ni.get_port(ed['dst_port'], is_input=True)
            if src_port and dst_port:
                self.connect_ports(src_port, dst_port)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _port_at(self, scene_pos, exclude=None):
        """Return the PortItem near scene_pos by iterating our own node list."""
        from .constants import PORT_HIT_RADIUS
        r2 = PORT_HIT_RADIUS * PORT_HIT_RADIUS
        for ni in self._node_items:
            ports = list(ni._input_ports.values()) + list(ni._output_ports.values())
            for port in ports:
                if port is exclude:
                    continue
                c  = port.scene_center()
                dx = scene_pos.x() - c.x()
                dy = scene_pos.y() - c.y()
                if dx * dx + dy * dy <= r2:
                    return port
        return None
