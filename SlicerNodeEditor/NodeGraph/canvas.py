"""
NodeEditorCanvas — QGraphicsView with pan/zoom, keyboard shortcuts,
and the Tab search popup.

Keyboard shortcuts
──────────────────
1 / 2        assign hovered node to viewer slot and activate it;
             if no node is hovered, recall the slot's last assignment
Tab          open node-search popup at cursor
Delete /
Backspace    delete selected nodes and their edges
F            frame selected nodes in view (or all nodes if nothing selected)
Escape       deselect all
"""

from PySide2.QtWidgets import QGraphicsView
from PySide2.QtCore    import Qt, QPointF
from PySide2.QtGui     import QPainter, QTransform

from .scene        import NodeEditorScene
from .node_item    import NodeItem
from .search_popup import SearchPopup


class NodeEditorCanvas(QGraphicsView):
    """
    Main canvas widget.  Embed with  layout.addWidget(canvas).

    Parameters
    ----------
    node_registry : list[SlicerBaseNode subclass]
        All node classes available in the Tab search menu.
    router : ViewerSlotManager
    executor : Executor
    """

    def __init__(self, node_registry, router, executor, parent=None):
        super().__init__(parent)

        self._registry     = node_registry
        self._router       = router
        self._executor     = executor
        self._popup        = None
        self._popup_scene_pos = QPointF(0, 0)

        # Scene
        self._scene = NodeEditorScene(self)
        self.setScene(self._scene)

        # View settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(self.NoFrame)

        # Dark background (belt-and-braces with the scene brush)
        self.setStyleSheet("background: rgb(26,26,26); border: none;")

        # Mouse tracking so we always know cursor position for Tab
        self.setMouseTracking(True)
        self._last_mouse_scene = QPointF(0, 0)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def node_scene(self):
        return self._scene

    def frame_all(self):
        items = self._scene.all_node_items()
        if items:
            rect = items[0].sceneBoundingRect()
            for ni in items[1:]:
                rect = rect.united(ni.sceneBoundingRect())
            self.fitInView(rect.adjusted(-40, -40, 40, 40),
                           Qt.KeepAspectRatio)

    def frame_selected(self):
        selected = [i for i in self._scene.selectedItems()
                    if isinstance(i, NodeItem)]
        if selected:
            rect = selected[0].sceneBoundingRect()
            for ni in selected[1:]:
                rect = rect.united(ni.sceneBoundingRect())
            self.fitInView(rect.adjusted(-40, -40, 40, 40),
                           Qt.KeepAspectRatio)
        else:
            self.frame_all()

    # ------------------------------------------------------------------
    # Mouse tracking for slot hotkeys and Tab position
    # ------------------------------------------------------------------

    def mouseMoveEvent(self, event):
        self._last_mouse_scene = self.mapToScene(event.pos())
        super().mouseMoveEvent(event)

    # ------------------------------------------------------------------
    # Middle-mouse pan
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            # Simulate left-button press for scroll-hand drag
            from PySide2.QtCore import QEvent
            from PySide2.QtGui  import QMouseEvent
            fake = QMouseEvent(QEvent.MouseButtonPress,
                               event.localPos(), event.screenPos(),
                               Qt.LeftButton, Qt.LeftButton,
                               event.modifiers())
            super().mousePressEvent(fake)
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            from PySide2.QtCore import QEvent
            from PySide2.QtGui  import QMouseEvent
            fake = QMouseEvent(QEvent.MouseButtonRelease,
                               event.localPos(), event.screenPos(),
                               Qt.LeftButton, Qt.LeftButton,
                               event.modifiers())
            super().mouseReleaseEvent(fake)
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def wheelEvent(self, event):
        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        self.scale(factor, factor)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        key = event.key()

        # --- Viewer slot routing ---
        if key in (Qt.Key_1, Qt.Key_2):
            slot      = 1 if key == Qt.Key_1 else 2
            hovered   = self._hovered_node()
            if hovered is not None:
                # Clear previous slot badge for this slot
                prev = self._router.get_slot_node(slot)
                if prev is not None:
                    prev.set_viewer_slot(None)
                hovered.set_viewer_slot(slot)
                self._router.assign_and_activate(hovered, slot)
            else:
                self._router.activate(slot)
            return

        # --- Tab: open node search popup ---
        if key == Qt.Key_Tab:
            self._open_search_popup()
            return

        # --- Delete selected nodes ---
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            self._delete_selected()
            return

        # --- Frame ---
        if key == Qt.Key_F:
            self.frame_selected()
            return

        # --- Deselect ---
        if key == Qt.Key_Escape:
            self._scene.clearSelection()
            return

        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Tab search popup
    # ------------------------------------------------------------------

    def _open_search_popup(self):
        if self._popup and self._popup.isVisible():
            self._popup.close()
            return

        scene_pos = self._last_mouse_scene
        self._popup = SearchPopup(self, scene_pos, self._registry)
        self._popup.node_chosen.connect(self._on_node_chosen)
        self._popup.show()

    def _on_node_chosen(self, node_class):
        """Place a new node at the position where Tab was pressed."""
        node_data = node_class()
        # Offset slightly so the node centre lands near the cursor
        from .constants import NODE_WIDTH, NODE_TITLE_HEIGHT, NODE_BODY_HEIGHT
        pos = self._popup._scene_pos - QPointF(
            NODE_WIDTH / 2,
            (NODE_TITLE_HEIGHT + NODE_BODY_HEIGHT) / 2)
        self._scene.add_node(node_data, pos)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _delete_selected(self):
        for item in list(self._scene.selectedItems()):
            if isinstance(item, NodeItem):
                self._router.clear_node(item)
                self._scene.remove_node(item)
            else:
                # Edge selected directly
                from .edge_item import EdgeItem
                if isinstance(item, EdgeItem):
                    self._scene.remove_edge(item)

    # ------------------------------------------------------------------
    # Hover detection for slot hotkeys
    # ------------------------------------------------------------------

    def _hovered_node(self):
        """Return the NodeItem under the mouse cursor, or None."""
        for item in self._scene.items(self._last_mouse_scene):
            if isinstance(item, NodeItem):
                return item
        return None
