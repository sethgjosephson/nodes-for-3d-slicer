"""
NodeItem — QGraphicsObject wrapping a SlicerBaseNode for canvas display.

Layout (vertical pipeline, top-to-bottom data flow):

    ● in0    ● in1          ← PortItems centred on top edge
  ┌────────────────────┐
  │▓▓ Node Name        │   ← coloured title bar
  ├────────────────────┤
  │  [dirty●] [①]      │   ← body: dirty dot + viewer-slot badge
  └────────────────────┘
       ● out0               ← PortItems centred on bottom edge

Selecting a node emits node_selected(self) on the scene.
"""

from PySide2.QtWidgets import QGraphicsObject
from PySide2.QtCore    import QRectF, QPointF, Qt, Signal
from PySide2.QtGui     import (QPainter, QColor, QPen, QBrush,
                                QPainterPath, QFont, QFontMetrics)

from .port_item import PortItem
from .constants import (
    NODE_WIDTH, NODE_TITLE_HEIGHT, NODE_BODY_HEIGHT, NODE_CORNER_RADIUS,
    NODE_BORDER_NORMAL, NODE_BORDER_SELECT,
    NODE_TITLE_FG, NODE_BODY_BG,
    NODE_DIRTY_COLOR, SLOT_BADGE_COLORS,
    CAT_COLOR, DEFAULT_CAT_COLOR,
    PORT_RADIUS,
)


class NodeItem(QGraphicsObject):
    """Visual node on the canvas.  Wraps a SlicerBaseNode (logic/data)."""

    # Emitted when this node is clicked; scene re-emits for the panel.
    selected_changed = Signal(object)   # self  (never None from here)

    def __init__(self, node_data, scene_pos=None):
        super().__init__()

        self.node_data    = node_data
        self._viewer_slot = None        # 1, 2, or None

        # Visual dimensions (recalculated once ports are built)
        n_in  = len(node_data.INPUT_PORTS)
        n_out = len(node_data.OUTPUT_PORTS)
        extra = max(0, max(n_in, n_out) - 3) * 6
        self._body_h = NODE_BODY_HEIGHT + extra
        self._total_h = NODE_TITLE_HEIGHT + self._body_h

        # Title-bar colour from category or explicit override
        cat_color = node_data.NODE_COLOR or CAT_COLOR.get(
            node_data.CATEGORY, DEFAULT_CAT_COLOR)
        self._title_color = QColor(*cat_color)

        # Build port items (child items → move with node)
        self._input_ports  = {}   # port_name → PortItem
        self._output_ports = {}

        self._build_ports(node_data.INPUT_PORTS,  is_input=True)
        self._build_ports(node_data.OUTPUT_PORTS, is_input=False)

        # Qt flags
        self.setFlag(self.ItemIsMovable,            True)
        self.setFlag(self.ItemIsSelectable,         True)
        self.setFlag(self.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(0)

        if scene_pos:
            self.setPos(scene_pos)

    # ------------------------------------------------------------------
    # QGraphicsItem
    # ------------------------------------------------------------------

    def boundingRect(self):
        # Inflate by PORT_RADIUS so port circles are inside the bounding box
        r = PORT_RADIUS
        return QRectF(-r, -r,
                      NODE_WIDTH + r * 2,
                      self._total_h + r * 2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        selected  = self.isSelected()
        body_rect = QRectF(0, 0, NODE_WIDTH, self._total_h)
        title_rect = QRectF(0, 0, NODE_WIDTH, NODE_TITLE_HEIGHT)

        # --- Body (full rounded rect) ---
        path = QPainterPath()
        path.addRoundedRect(body_rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
        painter.fillPath(path, QBrush(QColor(*NODE_BODY_BG)))

        # --- Title bar ---
        title_path = QPainterPath()
        title_path.addRoundedRect(title_rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
        # Clip bottom corners flat
        clip = QPainterPath()
        clip.addRect(QRectF(0, NODE_CORNER_RADIUS,
                            NODE_WIDTH, NODE_TITLE_HEIGHT))
        title_path = title_path.united(clip)
        painter.fillPath(title_path, QBrush(self._title_color))

        # --- Node name ---
        font = QFont("Arial", 9, QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(*NODE_TITLE_FG))
        fm    = QFontMetrics(font)
        name  = fm.elidedText(self.node_data.NODE_NAME,
                               Qt.ElideRight, NODE_WIDTH - 16)
        painter.drawText(QRectF(8, 0, NODE_WIDTH - 16, NODE_TITLE_HEIGHT),
                         Qt.AlignVCenter | Qt.AlignLeft, name)

        # --- Outline ---
        border_color = NODE_BORDER_SELECT if selected else NODE_BORDER_NORMAL
        painter.setPen(QPen(QColor(*border_color),
                            2.0 if selected else 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(body_rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)

        # --- Dirty indicator ---
        if self.node_data.is_dirty:
            dirty_r = 5
            painter.setBrush(QBrush(QColor(*NODE_DIRTY_COLOR)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(
                QPointF(NODE_WIDTH - dirty_r - 6,
                        NODE_TITLE_HEIGHT + self._body_h / 2),
                dirty_r, dirty_r)

        # --- Viewer-slot badge ---
        if self._viewer_slot is not None:
            badge_color = QColor(*SLOT_BADGE_COLORS.get(self._viewer_slot,
                                                        (160, 160, 160)))
            badge_r = 8
            cx = badge_r + 6
            cy = NODE_TITLE_HEIGHT + self._body_h / 2
            painter.setBrush(QBrush(badge_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cx, cy), badge_r, badge_r)
            font2 = QFont("Arial", 7, QFont.Bold)
            painter.setFont(font2)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                QRectF(cx - badge_r, cy - badge_r, badge_r * 2, badge_r * 2),
                Qt.AlignCenter, str(self._viewer_slot))

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        # Emit after Qt has updated isSelected()
        if event.button() == Qt.LeftButton:
            self.selected_changed.emit(self)

    # ------------------------------------------------------------------
    # Notify scene when node moves (edges need to repaint)
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged and self.scene():
            self.scene().on_node_moved(self)
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_port(self, port_name, is_input):
        if is_input:
            return self._input_ports.get(port_name)
        return self._output_ports.get(port_name)

    def all_input_ports(self):
        return list(self._input_ports.values())

    def all_output_ports(self):
        return list(self._output_ports.values())

    def set_property(self, name, value):
        """Called by the properties panel; propagates dirty downstream."""
        self.node_data.set_property(name, value)
        if self.scene():
            self.scene().mark_dirty_from(self)
        self.update()

    def set_viewer_slot(self, slot):
        """slot = 1, 2, or None."""
        self._viewer_slot = slot
        self.update()

    # ------------------------------------------------------------------
    # Port construction
    # ------------------------------------------------------------------

    def _build_ports(self, port_defs, is_input):
        count = len(port_defs)
        if count == 0:
            return

        for i, (pname, plabel, dtype) in enumerate(port_defs):
            port = PortItem(pname, plabel, dtype, is_input, self)
            x = self._port_x(i, count)
            y = 0 if is_input else self._total_h
            port.setPos(x, y)

            if is_input:
                self._input_ports[pname] = port
            else:
                self._output_ports[pname] = port

    @staticmethod
    def _port_x(index, count):
        """Evenly distribute ports across node width."""
        if count == 1:
            return NODE_WIDTH / 2
        spacing = NODE_WIDTH / (count + 1)
        return spacing * (index + 1)
