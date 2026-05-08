"""
NodeEditorScene — QGraphicsScene managing nodes, edges, and the
edge-drag state machine.

Topology queries used by Executor live here so neither NodeItem nor
Executor needs to know about the full graph.
"""

from PySide2.QtWidgets import QGraphicsScene
from PySide2.QtCore    import QPointF, Qt, Signal
from PySide2.QtGui     import QColor, QPainter, QBrush, QPen, QPixmap

from .node_item  import NodeItem
from .edge_item  import EdgeItem
from .port_item  import PortItem
from .constants  import (CANVAS_BG, GRID_DOT_COLOR, GRID_SPACING,
                          NODE_WIDTH, NODE_TITLE_HEIGHT, NODE_BODY_HEIGHT)


class NodeEditorScene(QGraphicsScene):
    """
    Central scene.  Owns the list of edges and drives the edge-drag
    state machine.

    Signals
    -------
    node_selected(NodeItem | None)
        Emitted when the canvas selection changes.
    """

    node_selected = Signal(object)   # NodeItem or None

    def __init__(self, parent=None):
        super().__init__(parent)

        self._edges            = []          # [EdgeItem]
        self._drag_edge        = None        # temp EdgeItem during drag
        self._drag_source_port = None        # PortItem where drag started

        self.setBackgroundBrush(QBrush(QColor(*CANVAS_BG)))
        self._dot_pixmap = self._build_dot_tile()

        # Pre-set a large scene rect so the grid fills the viewport
        self.setSceneRect(-4000, -4000, 8000, 8000)

    # ------------------------------------------------------------------
    # Background grid
    # ------------------------------------------------------------------

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
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
        item.selected_changed.connect(self._on_node_selected)
        self.addItem(item)
        return item

    def remove_node(self, node_item):
        """Remove node and all its connected edges."""
        for edge in self.edges_of(node_item):
            self.remove_edge(edge)
        self.removeItem(node_item)

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
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_edge is not None and event.button() == Qt.LeftButton:
            # Find port under cursor (exclude the drag source)
            target = self._port_at(event.scenePos(),
                                   exclude=self._drag_source_port)
            if target is not None:
                self.connect_ports(self._drag_source_port, target)

            self.removeItem(self._drag_edge)
            self._drag_edge        = None
            self._drag_source_port = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

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
        return [i for i in self.items() if isinstance(i, NodeItem)]

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
    # Selection handling
    # ------------------------------------------------------------------

    def _on_node_selected(self, node_item):
        self.node_selected.emit(node_item)

    def mousePressEvent(self, event):
        # Click on empty space → deselect and clear properties panel
        item = self.itemAt(event.scenePos(), self.views()[0].transform()
                           if self.views() else __import__('PySide2.QtGui',
                           fromlist=['QTransform']).QTransform())
        if item is None:
            self.clearSelection()
            self.node_selected.emit(None)
        super().mousePressEvent(event)

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
            nodes.append({
                'id':       i,
                'class':    ni.node_data.__class__.__name__,
                'module':   ni.node_data.__class__.__module__,
                'x':        ni.pos().x(),
                'y':        ni.pos().y(),
                'props':    dict(ni.node_data._props),
                'slot':     ni._viewer_slot,
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
            ni    = self.add_node(node, __import__('PySide2.QtCore',
                                  fromlist=['QPointF']).QPointF(nd['x'], nd['y']))
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
        """Return the PortItem nearest to scene_pos, or None."""
        for item in self.items(scene_pos):
            if isinstance(item, PortItem) and item is not exclude:
                return item
        return None
