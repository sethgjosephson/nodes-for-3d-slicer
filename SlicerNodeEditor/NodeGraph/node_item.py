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

import time

from ._qt import (QGraphicsObject, QRectF, QPointF, Qt, Signal,
                   QPainter, QColor, QPen, QBrush, QPainterPath, QFont, QFontMetrics)

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

        # Shake-to-disconnect tracking
        self._motion_history = []   # list of (time, x, y)

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

        selected   = self.isSelected()
        disabled   = bool(getattr(self.node_data, 'is_disabled', False))
        body_rect  = QRectF(0, 0, NODE_WIDTH, self._total_h)
        title_rect = QRectF(0, 0, NODE_WIDTH, NODE_TITLE_HEIGHT)

        # Dim the entire node when disabled. We restore opacity before
        # painting the strike-through marker so it stays vivid.
        if disabled:
            painter.setOpacity(0.45)

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
        painter.setBrush(QBrush())
        painter.drawRoundedRect(body_rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)

        # --- Dirty / computing indicator ---
        # An async-pending node trumps "dirty" — show blue with an ellipsis
        # so the user knows work is in flight. Dirty shows orange.
        async_pending = bool(getattr(self.node_data, '_async_pending', False))
        if async_pending or self.node_data.is_dirty:
            dirty_r = 5
            if async_pending:
                indicator_color = QColor(60, 160, 220)   # blue
                indicator_label = "…"
            else:
                indicator_color = QColor(*NODE_DIRTY_COLOR)
                indicator_label = ""
            cx = NODE_WIDTH - dirty_r - 6
            cy = NODE_TITLE_HEIGHT + self._body_h / 2
            painter.setBrush(QBrush(indicator_color))
            painter.setPen(QPen(Qt.NoPen))
            painter.drawEllipse(QPointF(cx, cy), dirty_r, dirty_r)
            if indicator_label:
                font_ind = QFont("Arial", 7, QFont.Bold)
                painter.setFont(font_ind)
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(
                    QRectF(cx - dirty_r, cy - dirty_r,
                           dirty_r * 2, dirty_r * 2),
                    Qt.AlignCenter, indicator_label)

        # --- Viewer-slot badge ---
        if self._viewer_slot is not None:
            badge_color = QColor(*SLOT_BADGE_COLORS.get(self._viewer_slot,
                                                        (160, 160, 160)))
            badge_r = 8
            cx = badge_r + 6
            cy = NODE_TITLE_HEIGHT + self._body_h / 2
            painter.setBrush(QBrush(badge_color))
            painter.setPen(QPen(Qt.NoPen))
            painter.drawEllipse(QPointF(cx, cy), badge_r, badge_r)
            font2 = QFont("Arial", 7, QFont.Bold)
            painter.setFont(font2)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                QRectF(cx - badge_r, cy - badge_r, badge_r * 2, badge_r * 2),
                Qt.AlignCenter, str(self._viewer_slot))

        # --- Disabled strike-through line (drawn at full opacity) ---
        if disabled:
            painter.setOpacity(1.0)
            strike_pen = QPen(QColor(220, 60, 60), 2.5, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(strike_pen)
            mid_y = NODE_TITLE_HEIGHT + self._body_h / 2
            painter.drawLine(QPointF(8,             mid_y),
                             QPointF(NODE_WIDTH - 8, mid_y))

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        # Single click only selects / starts drag — the left panel does
        # NOT update.  That happens on double-click.
        QGraphicsObject.mousePressEvent(self, event)

    def mouseDoubleClickEvent(self, event):
        QGraphicsObject.mouseDoubleClickEvent(self, event)
        if event.button() == Qt.LeftButton and self.scene() is not None:
            scene = self.scene()
            if hasattr(scene, 'notify_node_selected'):
                scene.notify_node_selected(self)

    def mouseReleaseEvent(self, event):
        QGraphicsObject.mouseReleaseEvent(self, event)
        # After drag ends, give the scene a chance to auto-insert this
        # node into a pipe if it was dropped on top of one.
        scene = self.scene()
        if scene is not None and hasattr(scene, 'try_insert_into_pipe'):
            scene.try_insert_into_pipe(self)

    # ------------------------------------------------------------------
    # Notify scene when node moves (edges need to repaint)
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged and self.scene():
            scene = self.scene()
            scene.on_node_moved(self)
            self._track_shake_motion(value)
            if hasattr(scene, 'update_drop_highlight'):
                scene.update_drop_highlight(self)
        try:
            return QGraphicsObject.itemChange(self, change, value)
        except Exception:
            return value

    def _track_shake_motion(self, pos):
        """Detect a 'shake' gesture and disconnect all edges if detected."""
        now    = time.time()
        cutoff = now - 0.4
        self._motion_history.append((now, pos.x(), pos.y()))
        while self._motion_history and self._motion_history[0][0] < cutoff:
            self._motion_history.pop(0)
        if len(self._motion_history) < 6:
            return

        # Total path length vs net displacement over last 0.4s
        path = 0.0
        for i in range(1, len(self._motion_history)):
            _, x1, y1 = self._motion_history[i - 1]
            _, x2, y2 = self._motion_history[i]
            path += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        _, x0, y0 = self._motion_history[0]
        _, xn, yn = self._motion_history[-1]
        net = ((xn - x0) ** 2 + (yn - y0) ** 2) ** 0.5

        # Shake = lots of motion that didn't actually go anywhere
        if path > 200 and (net < 1.0 or path / net > 5.0):
            scene = self.scene()
            if scene is not None and hasattr(scene, 'disconnect_all_edges'):
                scene.disconnect_all_edges(self)
            self._motion_history.clear()

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
        """Called by the properties panel; propagates dirty downstream and
        kicks off the debounced auto-rerun on the active viewer slot."""
        self.node_data.set_property(name, value)
        scene = self.scene()
        if scene is not None:
            scene.mark_dirty_from(self)
            if hasattr(scene, 'notify_property_changed'):
                scene.notify_property_changed(self)
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
