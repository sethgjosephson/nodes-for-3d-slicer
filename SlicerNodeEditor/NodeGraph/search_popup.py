"""
SearchPopup — Tab-key node-search overlay.

Press Tab anywhere on the canvas → popup appears at cursor.
Type to filter the node list, arrow-keys to navigate,
Enter or double-click to place the selected node, Escape to dismiss.
"""

from PySide2.QtWidgets import (QWidget, QVBoxLayout, QLineEdit,
                                QListWidget, QListWidgetItem, QFrame)
from PySide2.QtCore    import Qt, Signal, QPoint
from PySide2.QtGui     import QColor, QPalette, QFont

from .constants import (
    POPUP_WIDTH, POPUP_MAX_HEIGHT, POPUP_BG,
    POPUP_BORDER, POPUP_HIGHLIGHT,
)


class SearchPopup(QWidget):
    """
    Floating search widget for adding nodes to the canvas.

    Signals
    -------
    node_chosen(node_class)   emitted when user confirms a node choice
    """

    node_chosen = Signal(object)   # emits the SlicerBaseNode subclass

    def __init__(self, canvas, scene_pos, registry):
        """
        Parameters
        ----------
        canvas     : NodeEditorCanvas  (parent widget for positioning)
        scene_pos  : QPointF  scene coordinates where the new node will land
        registry   : list of SlicerBaseNode subclasses
        """
        super().__init__(canvas, Qt.Popup | Qt.FramelessWindowHint)

        self._scene_pos = scene_pos
        self._registry  = registry

        self._build_ui()
        self._populate(registry)
        self._apply_style()

        # Size and position
        self.setFixedWidth(POPUP_WIDTH)
        view_pt  = canvas.mapFromScene(scene_pos).toPoint()
        glob_pt  = canvas.mapToGlobal(view_pt)
        self.move(glob_pt)

        self._search.setFocus()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search nodes…")
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setMaximumHeight(POPUP_MAX_HEIGHT - 36)
        self._list.itemActivated.connect(self._on_activated)
        self._list.itemDoubleClicked.connect(self._on_activated)
        layout.addWidget(self._list)

        # Forward arrow-key navigation from the search box to the list
        self._search.installEventFilter(self)

    def _apply_style(self):
        bg  = "rgb({},{},{})".format(*POPUP_BG)
        bdr = "rgb({},{},{})".format(*POPUP_BORDER)
        hl  = "rgb({},{},{})".format(*POPUP_HIGHLIGHT)

        self.setStyleSheet(f"""
            QWidget {{
                background: {bg};
                color: rgb(210,210,210);
                border: 1px solid {bdr};
                border-radius: 4px;
            }}
            QLineEdit {{
                background: rgb(50,50,50);
                border: 1px solid {bdr};
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 11px;
            }}
            QListWidget {{
                background: transparent;
                border: none;
                font-size: 11px;
            }}
            QListWidget::item {{
                padding: 3px 6px;
                border-radius: 2px;
            }}
            QListWidget::item:selected {{
                background: {hl};
            }}
            QListWidget::item:hover {{
                background: rgb(60,60,60);
            }}
        """)

    # ------------------------------------------------------------------
    # Population and filtering
    # ------------------------------------------------------------------

    def _populate(self, registry):
        self._list.clear()
        # Group by category
        cats = {}
        for cls in registry:
            cats.setdefault(cls.CATEGORY, []).append(cls)

        for cat in sorted(cats):
            # Category header item (not selectable)
            hdr = QListWidgetItem(f"  {cat.upper()}")
            hdr.setFlags(Qt.NoItemFlags)
            hdr.setForeground(QColor(120, 120, 120))
            f = QFont()
            f.setPointSize(8)
            f.setBold(True)
            hdr.setFont(f)
            self._list.addItem(hdr)

            for cls in sorted(cats[cat], key=lambda c: c.NODE_NAME):
                item = QListWidgetItem(f"    {cls.NODE_NAME}")
                item.setData(Qt.UserRole, cls)
                self._list.addItem(item)

        # Pre-select the first real node
        self._select_first()

    def _filter(self, text):
        text = text.strip().lower()
        self._list.clear()

        if not text:
            self._populate(self._registry)
            return

        matches = [cls for cls in self._registry
                   if text in cls.NODE_NAME.lower()
                   or text in cls.CATEGORY.lower()]

        for cls in sorted(matches, key=lambda c: c.NODE_NAME):
            item = QListWidgetItem(cls.NODE_NAME)
            item.setData(Qt.UserRole, cls)
            self._list.addItem(item)

        self._select_first()

    def _select_first(self):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.flags() & Qt.ItemIsEnabled:
                self._list.setCurrentItem(item)
                return

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def _on_activated(self, item):
        cls = item.data(Qt.UserRole)
        if cls is not None:
            self.node_chosen.emit(cls)
            self.close()

    def _confirm_selection(self):
        item = self._list.currentItem()
        if item:
            self._on_activated(item)

    # ------------------------------------------------------------------
    # Event filter: arrow keys in search box move list selection
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        from PySide2.QtCore import QEvent
        if obj is self._search and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Down:
                self._move_selection(1)
                return True
            if key == Qt.Key_Up:
                self._move_selection(-1)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._confirm_selection()
                return True
            if key == Qt.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, event)

    def _move_selection(self, delta):
        row   = self._list.currentRow()
        count = self._list.count()
        # Skip non-selectable header rows
        new_row = row + delta
        while 0 <= new_row < count:
            item = self._list.item(new_row)
            if item.flags() & Qt.ItemIsEnabled:
                self._list.setCurrentRow(new_row)
                return
            new_row += delta
