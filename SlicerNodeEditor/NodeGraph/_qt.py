"""
Qt shim for the node-graph engine.

Slicer bundles Qt through PythonQt (import qt).  This module re-exports
every Qt class used by NodeGraph under the same names PySide2/PySide6 would
provide, plus a pure-Python Signal descriptor so classes can declare
signals without needing Qt's meta-object system.
"""

import qt

# ---------------------------------------------------------------------------
# Graphics
# ---------------------------------------------------------------------------
QGraphicsView        = qt.QGraphicsView
QGraphicsScene       = qt.QGraphicsScene
QGraphicsObject      = qt.QGraphicsObject
QGraphicsPathItem    = qt.QGraphicsPathItem
QGraphicsTextItem    = qt.QGraphicsTextItem

# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------
QWidget         = qt.QWidget
QVBoxLayout     = qt.QVBoxLayout
QLineEdit       = qt.QLineEdit
QListWidget     = qt.QListWidget
QListWidgetItem = qt.QListWidgetItem
QFrame          = qt.QFrame

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
Qt      = qt.Qt
QPointF = qt.QPointF
QRectF  = qt.QRectF
QPoint  = qt.QPoint
QEvent  = qt.QEvent

# ---------------------------------------------------------------------------
# Gui
# ---------------------------------------------------------------------------
QPainter            = qt.QPainter
QColor              = qt.QColor
QPen                = qt.QPen
QBrush              = qt.QBrush
QFont               = qt.QFont
QFontMetrics        = qt.QFontMetrics
QPainterPath        = qt.QPainterPath
QPainterPathStroker = qt.QPainterPathStroker
QTransform          = qt.QTransform
QPixmap             = qt.QPixmap
QPalette            = qt.QPalette


# ---------------------------------------------------------------------------
# Signal  (pure-Python descriptor, one instance per owner-object)
# ---------------------------------------------------------------------------

class _SignalInstance:
    __slots__ = ('_slots',)

    def __init__(self):
        self._slots = []

    def connect(self, slot):
        if slot not in self._slots:
            self._slots.append(slot)

    def disconnect(self, slot=None):
        if slot is None:
            self._slots.clear()
        elif slot in self._slots:
            self._slots.remove(slot)

    def emit(self, *args):
        for s in list(self._slots):
            s(*args)


class Signal:
    """
    Class-level descriptor that gives each instance its own _SignalInstance.

    Usage (identical to PySide2/PySide6):
        class Foo(SomeQtBase):
            bar = Signal(object)

        f = Foo()
        f.bar.connect(my_callback)
        f.bar.emit(value)
    """

    def __init__(self, *arg_types):
        self._attr = None          # set by __set_name__

    def __set_name__(self, owner, name):
        self._attr = '_signal_' + name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        key = self._attr or ('_signal_' + str(id(self)))
        try:
            inst = obj.__dict__.get(key)
        except AttributeError:
            # PythonQt objects may not expose __dict__; fall back to setattr
            inst = getattr(obj, key, None)
        if inst is None:
            inst = _SignalInstance()
            try:
                obj.__dict__[key] = inst
            except (AttributeError, TypeError):
                object.__setattr__(obj, key, inst)
        return inst
