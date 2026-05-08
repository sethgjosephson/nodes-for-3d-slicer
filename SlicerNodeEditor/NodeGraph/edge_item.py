"""
EdgeItem — QGraphicsPathItem drawing a bezier pipe between two ports.

When target_port is None the edge is a "drag preview" and its far end
follows self._float_end (a QPointF in scene coordinates).
"""

from PySide2.QtWidgets import QGraphicsPathItem
from PySide2.QtCore    import QPointF, Qt
from PySide2.QtGui     import QPainter, QPainterPath, QPen, QColor

from .constants import (
    EDGE_WIDTH, EDGE_CTRL_MIN, EDGE_DRAG_CLR,
    NODE_BODY_BG,
)


class EdgeItem(QGraphicsPathItem):
    """Bezier connection between an output port and an input port."""

    def __init__(self, source_port, target_port=None):
        super().__init__()

        self.source_port = source_port    # PortItem (output port)
        self.target_port = target_port    # PortItem (input port) or None
        self._float_end  = QPointF(0, 0) # used when target_port is None

        self.setZValue(1)               # below ports (z=2), above node body (z=0)
        self.setFlag(self.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        self._pen_normal   = self._make_pen(source_port)
        self._pen_selected = QPen(QColor(220, 220, 60), EDGE_WIDTH + 1.5,
                                  Qt.SolidLine, Qt.RoundCap)
        self._pen_drag     = QPen(QColor(*EDGE_DRAG_CLR), EDGE_WIDTH,
                                  Qt.DashLine, Qt.RoundCap)

        self.update_path()

    # ------------------------------------------------------------------
    # Path geometry
    # ------------------------------------------------------------------

    def update_path(self):
        """Recompute the bezier path from current port positions."""
        if self.source_port is None:
            return

        p1 = self.source_port.scene_center()

        if self.target_port is not None:
            p4 = self.target_port.scene_center()
        else:
            p4 = self._float_end

        dy          = abs(p4.y() - p1.y())
        ctrl_offset = max(EDGE_CTRL_MIN, dy * 0.5)

        # Source exits downward, target enters from above
        p2 = p1 + QPointF(0,  ctrl_offset)
        p3 = p4 - QPointF(0,  ctrl_offset)

        path = QPainterPath(p1)
        path.cubicTo(p2, p3, p4)
        self.setPath(path)

    def set_float_end(self, scene_pos: QPointF):
        """Update the floating (drag) end and repaint."""
        self._float_end = scene_pos
        self.update_path()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        if self.target_port is None:
            pen = self._pen_drag
        elif self.isSelected():
            pen = self._pen_selected
        else:
            pen = self._pen_normal

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

    def boundingRect(self):
        # Inflate base bounding rect to account for pen width
        return super().boundingRect().adjusted(-4, -4, 4, 4)

    def shape(self):
        # Wider hit area for easier selection/hover
        from PySide2.QtGui import QPainterPathStroker
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        return stroker.createStroke(self.path())

    # ------------------------------------------------------------------
    # Hover
    # ------------------------------------------------------------------

    def hoverEnterEvent(self, event):
        self._pen_normal.setWidth(EDGE_WIDTH + 1)
        self.update()

    def hoverLeaveEvent(self, event):
        self._pen_normal.setWidth(EDGE_WIDTH)
        self.update()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_pen(source_port):
        if source_port is not None:
            color = source_port.color
        else:
            color = QColor(*EDGE_DRAG_CLR)
        pen = QPen(color, EDGE_WIDTH, Qt.SolidLine, Qt.RoundCap)
        return pen
