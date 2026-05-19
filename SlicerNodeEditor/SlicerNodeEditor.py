"""
SlicerNodeEditor — Nuke-style node graph pipeline for 3D Slicer.

Module entry point.  The widget embeds the NodeEditorCanvas (PySide2
QGraphicsView) and a collapsible properties panel that shows the
selected node's parameters.
"""

import os
import json

import slicer
import ctk
import qt

from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleWidget,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleTest,
)
from slicer.util import VTKObservationMixin


# ---------------------------------------------------------------------------
# Module descriptor
# ---------------------------------------------------------------------------

class SlicerNodeEditor(ScriptedLoadableModule):
    def __init__(self, parent):
        super().__init__(parent)
        parent.title        = "Node Editor"
        parent.categories   = ["Utilities"]
        parent.dependencies = []
        parent.contributors = ["Seth Rivers"]
        parent.helpText = (
            "A Nuke-style node graph interface for 3D Slicer.\n\n"
            "• Tab     — search and place nodes\n"
            "• 1..9, 0 — assign selected node to viewer slot 1..10\n"
            "• Double-click a node — load its settings in the left panel\n"
            "• Ctrl+C/X/V — copy / cut / paste\n"
            "• Ctrl+Z/Y   — undo / redo\n"
            "• F       — frame nodes in view\n"
            "• D       — disable / enable selected nodes (passthrough)\n"
            "• Del     — delete selected nodes\n"
            "• Scroll — zoom  |  Middle-drag — pan"
        )
        parent.acknowledgementText = ""


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class SlicerNodeEditorWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):

    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        self._canvas         = None
        self._dock           = None
        self._props_widget   = None
        self._selected_node  = None
        self._startup_btn    = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self):
        super().setup()

        # --- Toolbar (Slicer-native Qt widgets, in module panel) -----
        toolbar_widget = qt.QWidget()
        toolbar_layout = qt.QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(0, 2, 0, 2)
        toolbar_layout.setSpacing(4)

        run_btn   = qt.QPushButton("▶  Execute All")
        save_btn  = qt.QPushButton("Save Graph")
        load_btn  = qt.QPushButton("Load Graph")
        clear_btn = qt.QPushButton("Clear")
        demo_btn  = qt.QPushButton("Demo")
        demo_btn.setToolTip(
            "Load a canned test workflow (three pipelines exercising filters, "
            "linked modules, and multi-VR visibility scoping).")

        # Checkable "Default" button: when on, Slicer opens to Node Editor
        # at next launch (writes "Modules/HomeModule" in QSettings).
        startup_btn = qt.QPushButton("Default on Launch")
        startup_btn.setCheckable(True)
        startup_btn.setToolTip(
            "If checked, Slicer will launch directly into Node Editor next time.")
        startup_btn.setChecked(self._is_default_startup_module())

        for btn in (run_btn, save_btn, load_btn, clear_btn, demo_btn,
                    startup_btn):
            btn.setMaximumHeight(24)
            toolbar_layout.addWidget(btn)
        toolbar_layout.addStretch()
        self._startup_btn = startup_btn

        self.layout.addWidget(toolbar_widget)

        # --- Canvas — lives in a bottom dock widget, NOT module panel
        from NodeGraph import NodeEditorCanvas, Executor, ViewerSlotManager
        from Nodes     import ALL_NODE_CLASSES

        self._router  = ViewerSlotManager()
        self._canvas  = NodeEditorCanvas(ALL_NODE_CLASSES, self._router, None)
        executor      = Executor(self._canvas.node_scene)
        self._router.set_executor(executor)
        self._canvas._executor = executor
        # Tell the scene about the router so undo/redo can rebind viewer slots
        self._canvas.node_scene.set_router(self._router)

        main_window = slicer.util.mainWindow()
        self._dock  = qt.QDockWidget("Node Editor", main_window)
        self._dock.setObjectName("NodeEditorDock")
        self._dock.setFeatures(
            qt.QDockWidget.DockWidgetMovable
            | qt.QDockWidget.DockWidgetFloatable
            | qt.QDockWidget.DockWidgetClosable)
        self._dock.setAllowedAreas(
            qt.Qt.BottomDockWidgetArea
            | qt.Qt.TopDockWidgetArea
            | qt.Qt.LeftDockWidgetArea
            | qt.Qt.RightDockWidgetArea)
        self._dock.setWidget(self._canvas)
        self._dock.setMinimumHeight(360)
        main_window.addDockWidget(qt.Qt.BottomDockWidgetArea, self._dock)
        self._dock.show()

        # --- Properties panel (collapsible, in module panel) ---------
        self._props_collapsible = ctk.ctkCollapsibleButton()
        self._props_collapsible.text      = "Node Properties"
        self._props_collapsible.collapsed = True
        self.layout.addWidget(self._props_collapsible)

        self._props_inner_layout = qt.QFormLayout(self._props_collapsible)
        self._props_inner_layout.setContentsMargins(8, 4, 8, 4)

        # Wire canvas → properties panel (direct callback, more reliable than Signal)
        self._canvas.node_scene.set_selection_listener(self._on_node_selected)

        # Toolbar actions
        run_btn.connect("clicked()",   self._on_execute_all)
        save_btn.connect("clicked()",  self._on_save)
        load_btn.connect("clicked()",  self._on_load)
        clear_btn.connect("clicked()", self._on_clear)
        demo_btn.connect("clicked()",  self._on_load_demo)
        startup_btn.connect("toggled(bool)", self._on_toggle_default_startup)

        # When the user closes the scene (or opens a different .mrb),
        # drop every node's cached MRML pointers and mark all nodes
        # dirty. The graph itself (nodes / edges / positions / props /
        # undo / clipboard / slots) is a recipe and survives untouched.
        # Pressing 1 in the new scene will re-cook the data.
        # StartCloseEvent fires BEFORE nodes are deleted, which is the
        # right moment to drop references.
        self.addObserver(slicer.mrmlScene,
                         slicer.vtkMRMLScene.StartCloseEvent,
                         self._on_scene_close)

    # ------------------------------------------------------------------
    # Properties panel
    # ------------------------------------------------------------------

    def _on_node_selected(self, node_item):
        self._selected_node = node_item

        # If the node is linked to a Slicer module, swap the left panel
        # to that module's own widget instead of building our inline form.
        linked = (getattr(node_item.node_data, 'LINKED_MODULE', None)
                  if node_item is not None else None)
        if linked:
            self._show_linked_module(node_item, linked)
            return

        # Otherwise: ensure we're on the Node Editor module and rebuild
        # the inline properties panel.
        self._ensure_node_editor_active()
        self._rebuild_props_panel(node_item)

    def _show_linked_module(self, node_item, module_name):
        """Switch Slicer to module_name and let the node configure it."""
        try:
            slicer.util.selectModule(module_name)
        except Exception as exc:
            print(f"[NodeEditor] selectModule('{module_name}') failed: {exc}")
            return

        try:
            mod = getattr(slicer.modules, module_name.lower(), None)
            if mod is None:
                return
            mw = mod.widgetRepresentation()
            if mw is None:
                return
            node_item.node_data.configure_module_widget(mw, node_item)
        except Exception as exc:
            import traceback; traceback.print_exc()
            print(f"[NodeEditor] configure_module_widget failed: {exc}")

    def _ensure_node_editor_active(self):
        """Switch back to this module if we're elsewhere (e.g. after VR)."""
        try:
            sel = slicer.app.moduleManager().moduleSelector()
            current = getattr(sel, 'selectedModule', None) or \
                      (sel.selectedModule() if callable(getattr(sel, 'selectedModule', None)) else '')
            if current != 'SlicerNodeEditor':
                slicer.util.selectModule('SlicerNodeEditor')
        except Exception:
            try:
                slicer.util.selectModule('SlicerNodeEditor')
            except Exception:
                pass

    def _rebuild_props_panel(self, node_item):
        """Populate the properties panel for the selected node."""
        # Clear existing widgets
        while self._props_inner_layout.count():
            child = self._props_inner_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if node_item is None:
            self._props_collapsible.collapsed = True
            return

        self._props_collapsible.text      = f"Properties — {node_item.node_data.NODE_NAME}"
        self._props_collapsible.collapsed = False

        # Give the node a chance to provide a fully-custom widget
        try:
            custom = node_item.node_data.build_properties_widget(
                self._props_collapsible, node_item)
        except Exception as exc:
            import traceback; traceback.print_exc()
            custom = None
        if custom is not None:
            self._props_inner_layout.addRow(custom)
            return

        for prop in node_item.node_data.PROPERTIES:
            label = qt.QLabel(prop['label'] + ":")
            widget = self._make_property_widget(prop, node_item)
            if widget:
                self._props_inner_layout.addRow(label, widget)

    def _make_property_widget(self, prop, node_item):
        """Build an appropriate Qt widget for a property definition."""
        name    = prop['name']
        ptype   = prop['type']
        current = node_item.node_data.get_property(name)

        if ptype == 'float':
            w = qt.QDoubleSpinBox()
            w.setMinimum(prop.get('min', -1e9))
            w.setMaximum(prop.get('max',  1e9))
            w.setSingleStep(0.1)
            w.setDecimals(3)
            w.setValue(float(current))
            w.connect('valueChanged(double)',
                      lambda v, n=name, ni=node_item: ni.set_property(n, v))
            return w

        if ptype == 'int':
            w = qt.QSpinBox()
            w.setMinimum(int(prop.get('min', -999999)))
            w.setMaximum(int(prop.get('max',  999999)))
            w.setValue(int(current))
            w.connect('valueChanged(int)',
                      lambda v, n=name, ni=node_item: ni.set_property(n, v))
            return w

        if ptype == 'str':
            w = qt.QLineEdit(str(current))
            w.connect('textChanged(const QString&)',
                      lambda v, n=name, ni=node_item: ni.set_property(n, v))
            # File-browser button for paths
            if 'path' in name.lower():
                container = qt.QWidget()
                hl        = qt.QHBoxLayout(container)
                hl.setContentsMargins(0, 0, 0, 0)
                hl.addWidget(w)
                browse = qt.QPushButton("…")
                browse.setMaximumWidth(28)
                def _browse(line_edit=w):
                    path = qt.QFileDialog.getOpenFileName(None, "Select file")
                    if path:
                        line_edit.setText(path)
                browse.connect('clicked()', _browse)
                hl.addWidget(browse)
                return container
            return w

        if ptype == 'enum':
            w = qt.QComboBox()
            for item in prop.get('items', []):
                w.addItem(item)
            idx = prop.get('items', []).index(current) \
                  if current in prop.get('items', []) else 0
            w.setCurrentIndex(idx)
            w.connect('currentTextChanged(const QString&)',
                      lambda v, n=name, ni=node_item: ni.set_property(n, v))
            return w

        if ptype == 'bool':
            w = qt.QCheckBox()
            w.setChecked(bool(current))
            w.connect('toggled(bool)',
                      lambda v, n=name, ni=node_item: ni.set_property(n, v))
            return w

        return None

    # ------------------------------------------------------------------
    # Toolbar actions
    # ------------------------------------------------------------------

    def _on_execute_all(self):
        from NodeGraph import Executor
        try:
            executor = Executor(self._canvas.node_scene)
            executor.execute_all()
        except Exception as exc:
            slicer.util.errorDisplay(f"Pipeline execution failed:\n{exc}")

    def _on_save(self):
        path = qt.QFileDialog.getSaveFileName(
            None, "Save Node Graph", "", "JSON (*.json)")[0]
        if not path:
            return
        data = self._canvas.node_scene.serialise()
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        slicer.util.infoDisplay(f"Graph saved to:\n{path}")

    def _on_load(self):
        path = qt.QFileDialog.getOpenFileName(
            None, "Load Node Graph", "", "JSON (*.json)")[0]
        if not path:
            return
        with open(path) as f:
            data = json.load(f)
        self._canvas.node_scene.deserialise(data, self._router)

    # ------------------------------------------------------------------
    # Default-startup-module toggle
    # ------------------------------------------------------------------

    _STARTUP_SETTING_KEY = 'Modules/HomeModule'
    _STARTUP_MODULE_NAME = 'SlicerNodeEditor'

    def _is_default_startup_module(self):
        """True if Slicer is currently configured to open into us."""
        try:
            current = slicer.app.userSettings().value(self._STARTUP_SETTING_KEY)
            return current == self._STARTUP_MODULE_NAME
        except Exception:
            return False

    def _on_toggle_default_startup(self, checked):
        """Toolbar checkbox: write the home-module setting."""
        try:
            settings = slicer.app.userSettings()
            if checked:
                settings.setValue(self._STARTUP_SETTING_KEY,
                                  self._STARTUP_MODULE_NAME)
                slicer.util.showStatusMessage(
                    "Node Editor will be the startup module next launch.",
                    3000)
            else:
                # Clear our specific value rather than wiping the key
                # entirely (Slicer falls back to its default if empty).
                settings.remove(self._STARTUP_SETTING_KEY)
                slicer.util.showStatusMessage(
                    "Startup module reverted to Slicer default.", 3000)
        except Exception as exc:
            slicer.util.errorDisplay(
                f"Could not update startup-module setting:\n{exc}")
            # Roll the checkbox back to match actual state
            if self._startup_btn is not None:
                self._startup_btn.setChecked(self._is_default_startup_module())

    def _on_load_demo(self):
        """Load the bundled demo workflow so we have a known-good test
        layout one click away after a reload."""
        demo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'Resources', 'demo_workflow.json')
        if not os.path.exists(demo_path):
            slicer.util.errorDisplay(
                f"Demo workflow not found:\n{demo_path}")
            return
        try:
            with open(demo_path) as f:
                data = json.load(f)
        except Exception as exc:
            slicer.util.errorDisplay(f"Could not read demo workflow:\n{exc}")
            return
        # Wipe whatever's currently on the canvas, then deserialise
        self._clear_graph()
        try:
            self._canvas.node_scene.deserialise(data, self._router)
        except Exception as exc:
            import traceback; traceback.print_exc()
            slicer.util.errorDisplay(f"Could not load demo workflow:\n{exc}")

    def _on_clear(self):
        """Toolbar Clear button: user-initiated, wipe everything."""
        self._clear_graph()

    def _on_scene_close(self, caller=None, event=None):
        """
        The MRML scene is about to be wiped (File > Close Scene, or
        opening a different .mrb).  The graph itself is a recipe and
        survives, but every node's cached MRML pointers are about to
        become dangling.  Drop those caches and mark every node dirty
        so the next press-1 re-cooks the data from upstream.

        Graph structure, edges, positions, properties, undo / redo
        stacks, the clipboard, and viewer slot bindings all stay intact
        (none of them reference MRML by identity).
        """
        if self._canvas is None:
            return
        scene = self._canvas.node_scene
        if scene is None:
            return
        try:
            for ni in scene.all_node_items():
                nd = ni.node_data
                # Drop input MRML observers BEFORE the underlying nodes
                # get deleted, so we don't try to RemoveObserver on dead
                # pointers later.
                try:
                    nd._clear_input_observers()
                except Exception:
                    pass
                # Forget every cached MRML pointer
                try:
                    nd._cache.clear()
                except Exception:
                    pass
                # SampleDataNode tracks multi-node loads by ID; reset that
                if hasattr(nd, '_loaded_node_ids'):
                    nd._loaded_node_ids = []
                nd.is_dirty = True
                try:
                    ni.update()  # repaint to show the dirty indicator
                except Exception:
                    pass
        except Exception:
            import traceback; traceback.print_exc()

    def _clear_graph(self):
        """Tear down every node, reset router slots, clear undo / redo /
        clipboard, and blank the properties panel.  Used by the Clear
        toolbar button — the explicit "throw it all away" action."""
        scene = self._canvas.node_scene if self._canvas is not None else None
        if scene is None:
            return
        for ni in list(scene.all_node_items()):
            scene.remove_node(ni)
        # Reset viewer slot bindings
        if self._router is not None:
            try:
                self._router._slots = {i: None for i in range(1, 11)}
            except Exception:
                pass
        # Clear undo / redo (everything we'd restore is now stale)
        try:
            scene._undo_stack.clear()
            scene._redo_stack.clear()
        except Exception:
            pass
        # Clear the cross-canvas clipboard too
        try:
            import NodeGraph.canvas as _canvas_mod
            _canvas_mod._CLIPBOARD = None
        except Exception:
            pass
        # Clear the properties panel
        try:
            self._rebuild_props_panel(None)
        except Exception:
            pass

    # ------------------------------------------------------------------

    def enter(self):
        # Bring the canvas dock to the front when the user is on this module,
        # but never hide it — the canvas is meant to be persistent across modules.
        if self._dock is not None:
            self._dock.show()
            self._dock.raise_()

    def exit(self):
        # Intentionally do NOT hide the dock — keep it visible across modules.
        pass

    def cleanup(self):
        if self._dock is not None:
            try:
                slicer.util.mainWindow().removeDockWidget(self._dock)
                self._dock.deleteLater()
            except Exception:
                pass
            self._dock = None
        self.removeObservers()


# ---------------------------------------------------------------------------
# Logic  (thin stub — all logic lives in the graph/nodes)
# ---------------------------------------------------------------------------

class SlicerNodeEditorLogic(ScriptedLoadableModuleLogic):
    pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class SlicerNodeEditorTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear()

    def runTest(self):
        self.setUp()
        self.test_SceneCreation()
        self.test_NodePlacement()
        self.test_EdgeConnection()

    def test_SceneCreation(self):
        self.delayDisplay("Testing scene creation")
        from NodeGraph import NodeEditorScene
        scene = NodeEditorScene()
        self.assertIsNotNone(scene)
        self.delayDisplay("Scene creation OK")

    def test_NodePlacement(self):
        self.delayDisplay("Testing node placement")
        from NodeGraph import NodeEditorScene
        from Nodes     import LoadVolumeNode
        from NodeGraph._qt import QPointF
        scene = NodeEditorScene()
        ni = scene.add_node(LoadVolumeNode(), QPointF(0, 0))
        self.assertEqual(len(scene.all_node_items()), 1)
        scene.remove_node(ni)
        self.assertEqual(len(scene.all_node_items()), 0)
        self.delayDisplay("Node placement OK")

    def test_EdgeConnection(self):
        self.delayDisplay("Testing edge connection")
        from NodeGraph import NodeEditorScene
        from Nodes     import LoadVolumeNode, ThresholdNode
        from NodeGraph._qt import QPointF
        scene = NodeEditorScene()
        src = scene.add_node(LoadVolumeNode(),  QPointF(0,   0))
        dst = scene.add_node(ThresholdNode(),   QPointF(0, 200))
        out_port = src.get_port('volume_out', is_input=False)
        in_port  = dst.get_port('volume_in',  is_input=True)
        edge = scene.connect_ports(out_port, in_port)
        self.assertIsNotNone(edge)
        self.delayDisplay("Edge connection OK")
