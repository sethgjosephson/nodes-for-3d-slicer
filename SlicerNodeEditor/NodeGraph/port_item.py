"""
PortItem — QGraphicsObject representing a single input or output port.

Ports live as child items of NodeItem and are positioned on its top edge
(inputs) or bottom edge (outputs).  Dragging from a port begins edge
creation; releasing on a compatible port finalises the connection.
"""

from ._qt import (QGraphicsObject, QGraphicsTextItem, QRectF, QPointF, Qt, Signal,
                   QPainter, QColor, QPen, QBrush, QFont)

from .constants import (
    PORT_RADIUS, PORT_HIT_RADIUS, PORT_COLORS,
    PORT_LABEL_FONT_SZ, NODE_BODY_BG,
)


class PortItem(QGraphicsObject):
    """Visual representation of one input or output port on a node."""

    drag_started   = Signal(object)          # emits self when drag begins
    drop_attempted = Signal(object, object)  # (source_port, target_port)

    def __init__(self, port_name, label, data_type, is_input, node_item):
        super().__init__(node_item)

        self.port_name  = port_name
        self.label      = label
        self.data_type  = data_type.lower()
        self.is_input   = is_input
        self.node_item  = node_item          # back-reference

        self._hovered   = False
        self._color     = QColor(*PORT_COLORS.get(self.data_type,
                                                   PORT_COLORS['any']))

        self.setAcceptHoverEvents(True)
        self.setZValue(2)                    # above node body

        # Label drawn as a child text item
        self._label_item = QGraphicsTextItem(label, self)
        font = QFont("Arial", PORT_LABEL_FONT_SZ)
        self._label_item.setFont(font)
        self._label_item.setDefaultTextColor(QColor(180, 180, 180))
        self._position_label()

    # ------------------------------------------------------------------
    # QGraphicsItem interface
    # ------------------------------------------------------------------

    def boundingRect(self):
        r = PORT_HIT_RADIUS
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        radius = PORT_RADIUS + (2 if self._hovered else 0)

        # Fill
        painter.setBrush(QBrush(self._color))
        # Outline — dark ring so port stands out against node edge
        painter.setPen(QPen(QColor(*NODE_BODY_BG), 2))
        painter.drawEllipse(QPointF(0, 0), radius, radius)

    # ------------------------------------------------------------------
    # Hover
    # ------------------------------------------------------------------

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    # ------------------------------------------------------------------
    # Drag-to-connect
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            event.accept()
            scene = self.scene()
            if scene is not None:
                scene.start_edge_drag(self)
        else:
            QGraphicsObject.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        # The scene's mouseReleaseEvent handles finalising the connection.
        event.accept()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _position_label(self):
        """Place label to the right of input ports, left of output ports."""
        tw = self._label_item.boundingRect().width()
        th = self._label_item.boundingRect().height()
        offset = PORT_RADIUS + 4
        if self.is_input:
            self._label_item.setPos(offset, -th / 2)
        else:
            self._label_item.setPos(-offset - tw, -th / 2)

    def scene_center(self):
        """Return this port's centre in scene coordinates."""
        return self.mapToScene(QPointF(0, 0))

    @property
    def color(self):
        return self._color
