"""
NodeEditorCanvas — QGraphicsView with pan/zoom, keyboard shortcuts,
and the Tab search popup.

Keyboard shortcuts
──────────────────
1 / 2        assign the currently-selected node to viewer slot and
             activate it; if nothing is selected, recall the slot's
             last assignment (toggle-style)
Tab          open node-search popup at cursor
Delete /
Backspace    delete selected nodes and their edges
F            frame selected nodes in view (or all nodes if nothing selected)
Escape       deselect all
"""

from ._qt import QGraphicsView, Qt, QPointF, QPoint, QPainter, QTransform

from .scene        import NodeEditorScene
from .node_item    import NodeItem
from .search_popup import SearchPopup


# Module-level clipboard so cut/copy survives across canvas instances
_CLIPBOARD = None


def _event_modifiers(event):
    """PythonQt-safe accessor for QKeyEvent modifiers (property OR method)."""
    m = event.modifiers
    if callable(m):
        try:
            m = m()
        except Exception:
            m = 0
    try:
        return int(m)
    except Exception:
        return 0


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
        self._pan_active       = False
        self._pan_origin       = QPoint(0, 0)

        # Auto-rerun on property change: when ANY node's property changes
        # we re-cook whichever pipeline is currently routed to the active
        # viewer slot. Debounced via QTimer so sliders don't trigger one
        # execution per pixel of drag.
        self._auto_rerun_timer = None
        self._auto_rerun_delay = 300  # ms
        try:
            self._scene.set_property_change_listener(self._on_property_changed)
        except Exception:
            pass

        # Capture Tab and other keys (default focus policy doesn't accept Tab)
        self.setFocusPolicy(Qt.StrongFocus)

    def focusNextPrevChild(self, next):
        # Prevent Qt from stealing Tab for focus traversal — we want it
        return False

    def enterEvent(self, event):
        # Auto-focus on hover so keyboard shortcuts work without a click first
        self.setFocus(Qt.MouseFocusReason)
        QGraphicsView.enterEvent(self, event)

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
        selected = self._scene.selected_node_items()
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
        if self._pan_active:
            pos = event.pos()
            dx  = pos.x() - self._pan_origin.x()
            dy  = pos.y() - self._pan_origin.y()
            self._pan_origin = pos
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value - dx)
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value - dy)
            event.accept()
            return
        QGraphicsView.mouseMoveEvent(self, event)

    # ------------------------------------------------------------------
    # Middle-mouse pan (scroll-bar based — avoids QMouseEvent construction)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._pan_active = True
            self._pan_origin = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        QGraphicsView.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._pan_active:
            self._pan_active = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        QGraphicsView.mouseReleaseEvent(self, event)

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
        key  = event.key()
        mods = _event_modifiers(event)
        ctrl = bool(mods & int(Qt.ControlModifier))

        # --- Edit shortcuts ---
        if ctrl and key == Qt.Key_Z:
            self._scene.undo()
            return
        if ctrl and key == Qt.Key_Y:
            self._scene.redo()
            return
        if ctrl and key == Qt.Key_C:
            self._copy_to_clipboard()
            return
        if ctrl and key == Qt.Key_X:
            self._cut_to_clipboard()
            return
        if ctrl and key == Qt.Key_V:
            self._paste_from_clipboard()
            return

        # --- Viewer slot routing (1..9 → slots 1..9, 0 → slot 10) ---
        slot_for_key = {
            Qt.Key_1: 1, Qt.Key_2: 2, Qt.Key_3: 3, Qt.Key_4: 4,
            Qt.Key_5: 5, Qt.Key_6: 6, Qt.Key_7: 7, Qt.Key_8: 8,
            Qt.Key_9: 9, Qt.Key_0: 10,
        }
        if key in slot_for_key:
            slot     = slot_for_key[key]
            selected = self._selected_node()
            if selected is not None:
                prev = self._router.get_slot_node(slot)
                if prev is not None and prev is not selected:
                    prev.set_viewer_slot(None)
                selected.set_viewer_slot(slot)
                self._router.assign_and_activate(selected, slot)
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

        # --- Frame canvas / Fullscreen selected output ---
        # F on a selected node routes its output to a single-pane
        # viewer (3D-only for VR, single slice for volumes, etc).
        # F with no selection frames the canvas viewport to fit nodes.
        if key == Qt.Key_F:
            sel = self._selected_node()
            if sel is not None:
                self._fullscreen_selected(sel)
            else:
                self.frame_selected()
            return

        # --- Deselect ---
        if key == Qt.Key_Escape:
            self._scene.clearSelection()
            return

        # --- Disable / enable selected nodes (compositor-style D) ---
        if key == Qt.Key_D and not ctrl:
            self._toggle_disable_selected()
            return

        QGraphicsView.keyPressEvent(self, event)

    # ------------------------------------------------------------------
    # Tab search popup
    # ------------------------------------------------------------------

    def _open_search_popup(self):
        if self._popup and self._popup.isVisible():
            self._popup.close()
            return

        scene_pos = self._last_mouse_scene
        self._popup = SearchPopup(self, scene_pos, self._registry,
                                  on_choose=self._on_node_chosen)
        self._popup.show()

    def _on_node_chosen(self, node_class):
        """Place a new node at the position where Tab was pressed."""
        from .constants import NODE_WIDTH, NODE_TITLE_HEIGHT, NODE_BODY_HEIGHT
        try:
            node_data = node_class()
        except Exception as exc:
            import slicer
            slicer.util.errorDisplay(
                f"Could not instantiate '{node_class.__name__}':\n{exc}")
            return

        # Capture the previously-selected node BEFORE we change selection
        prev_selected = self._selected_node()

        sp  = self._popup._scene_pos if self._popup else QPointF(0, 0)
        pos = QPointF(sp.x() - NODE_WIDTH / 2,
                      sp.y() - (NODE_TITLE_HEIGHT + NODE_BODY_HEIGHT) / 2)
        # Snapshot for undo before mutating the graph
        self._scene.capture_undo()
        try:
            new_item = self._scene.add_node(node_data, pos)
        except Exception as exc:
            import slicer
            import traceback
            slicer.util.errorDisplay(
                f"Could not add node to scene:\n{exc}\n\n"
                f"{traceback.format_exc()}")
            return

        # If a node was selected, auto-wire the new one after it
        if prev_selected is not None:
            try:
                self._scene.try_auto_connect(prev_selected, new_item)
            except Exception:
                import traceback; traceback.print_exc()

        # Switch selection to the new node
        self._scene.clearSelection()
        new_item.setSelected(True)
        self._scene.notify_node_selected(new_item)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _delete_selected(self):
        selected = list(self._scene.selected_node_items())
        if not selected:
            return
        self._scene.capture_undo()
        self._delete_with_splice(selected)

    def _fullscreen_selected(self, node_item):
        """Make sure the chain feeding this node is up-to-date, then
        ask the node to route its output to a single-pane fullscreen
        layout (3D-only for VR, single slice for volume outputs, etc)."""
        if self._executor is not None:
            try:
                self._executor.execute_up_to(node_item)
            except Exception as exc:
                import slicer
                slicer.util.errorDisplay(
                    f"Execution failed before fullscreen routing:\n{exc}")
                return
        try:
            node_item.node_data.route_fullscreen()
        except Exception as exc:
            import slicer
            slicer.util.errorDisplay(
                f"Fullscreen routing failed:\n{exc}")

    def _toggle_disable_selected(self):
        """Toggle the compositor-style 'disabled' flag on every selected node.
        Disabled nodes skip their own work and passthrough the first
        type-compatible input to each output, so downstream sees the
        unprocessed upstream data. Useful for quick A/B comparisons."""
        selected = self._scene.selected_node_items()
        if not selected:
            return
        self._scene.capture_undo()
        for ni in selected:
            ni.node_data.is_disabled = not getattr(
                ni.node_data, 'is_disabled', False)
            # Disabling/enabling changes the node's output, so mark
            # downstream dirty and the node itself dirty.
            ni.node_data.is_dirty = True
            ni.update()
            self._scene.mark_dirty_from(ni)
        # Schedule the auto-rerun so the currently-viewed pipeline
        # reflects the new on/off state right away.
        self._schedule_auto_rerun()

    def _delete_with_splice(self, items):
        """Delete each item; if it sits in a pipe, splice the pipe back
        together (upstream port → downstream port directly)."""
        sel_set = {id(ni) for ni in items}
        for ni in items:
            plan = self._scene.build_splice_out_plan(ni)
            # Skip pairs where either side belongs to another being-deleted node
            plan = [(u, d) for u, d in plan
                    if id(u.node_item) not in sel_set
                    and id(d.node_item) not in sel_set]
            self._router.clear_node(ni)
            self._scene.remove_node(ni)
            for up, down in plan:
                self._scene.connect_ports(up, down)

    # ------------------------------------------------------------------
    # Clipboard (copy / cut / paste)
    # ------------------------------------------------------------------

    def _copy_to_clipboard(self):
        global _CLIPBOARD
        clip = self._scene.copy_selection()
        if clip:
            _CLIPBOARD = clip

    def _cut_to_clipboard(self):
        global _CLIPBOARD
        clip = self._scene.copy_selection()
        if not clip:
            return
        _CLIPBOARD = clip
        self._scene.capture_undo()
        self._delete_with_splice(list(self._scene.selected_node_items()))

    def _paste_from_clipboard(self):
        if not _CLIPBOARD:
            return
        # Capture currently-selected node BEFORE paste flips selection
        prev_selected = self._selected_node()

        self._scene.capture_undo()
        new_items = self._scene.paste_clipboard(_CLIPBOARD,
                                                self._last_mouse_scene)

        # Auto-connect: feed prev_selected's output into the pasted graph's entry
        if prev_selected is not None and new_items:
            entry = self._find_paste_entry(new_items)
            if entry is not None:
                try:
                    self._scene.try_auto_connect(prev_selected, entry)
                except Exception:
                    import traceback; traceback.print_exc()

        # Notify props panel about the first pasted node so the user has context
        if new_items:
            self._scene.notify_node_selected(new_items[0])

    def _find_paste_entry(self, new_items):
        """Pick the first pasted node that has an unfilled input port —
        the natural 'entry' for piping the previously-selected node into."""
        for ni in new_items:
            if not ni.node_data.INPUT_PORTS:
                continue
            for port_name, _label, _dtype in ni.node_data.INPUT_PORTS:
                in_port = ni.get_port(port_name, is_input=True)
                if in_port is not None and self._scene.get_incoming_edge(in_port) is None:
                    return ni
        return None

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _selected_node(self):
        """Return the (single) selected NodeItem, or None."""
        sel = self._scene.selected_node_items()
        return sel[0] if sel else None

    # ------------------------------------------------------------------
    # Auto-rerun on property change (procedural live-update)
    # ------------------------------------------------------------------

    def _on_property_changed(self, node_item):
        """Scene tells us a node's property was edited. Debounce-schedule
        a re-cook of the active viewer slot's pipeline."""
        self._schedule_auto_rerun()

    def _schedule_auto_rerun(self):
        """(Re)start the auto-rerun debounce timer."""
        import qt
        if self._auto_rerun_timer is None:
            self._auto_rerun_timer = qt.QTimer()
            self._auto_rerun_timer.setSingleShot(True)
            self._auto_rerun_timer.timeout.connect(self._do_auto_rerun)
        self._auto_rerun_timer.start(self._auto_rerun_delay)

    def _do_auto_rerun(self):
        """Re-execute the active viewer slot's pipeline IF every dirty
        ancestor allows it (AUTO_EXECUTE is True and not async-pending)."""
        if self._router is None:
            return
        slot = self._router._active
        target = self._router.get_slot_node(slot)
        if target is None:
            return  # no active viewer to update
        if not self._can_auto_run(target):
            return  # expensive ancestor in the chain; wait for manual press-1
        try:
            self._router.activate(slot)
        except Exception:
            import traceback; traceback.print_exc()

    def _can_auto_run(self, target_node_item):
        """Walk dirty ancestors of `target`; return False if any node in
        the chain has opted out of auto-execution (AUTO_EXECUTE=False)
        or is currently async-pending."""
        if self._executor is None:
            return False
        try:
            ancestors = self._executor._ancestors_including(target_node_item)
        except Exception:
            return False
        for ni in ancestors:
            nd = ni.node_data
            if getattr(nd, '_async_pending', False):
                return False
            if nd.is_dirty and not getattr(nd, 'AUTO_EXECUTE', True):
                return False
        return True
