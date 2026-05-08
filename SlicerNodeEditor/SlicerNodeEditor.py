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
            "• Tab  — search and place nodes\n"
            "• 1/2  — route hovered node to viewer slot 1 or 2\n"
            "• F    — frame nodes in view\n"
            "• Del  — delete selected nodes\n"
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
        self._props_widget   = None
        self._selected_node  = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self):
        super().setup()

        # --- Toolbar (Slicer-native Qt widgets) ----------------------
        toolbar_widget = qt.QWidget()
        toolbar_layout = qt.QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(0, 2, 0, 2)
        toolbar_layout.setSpacing(4)

        run_btn   = qt.QPushButton("▶  Execute All")
        save_btn  = qt.QPushButton("Save Graph")
        load_btn  = qt.QPushButton("Load Graph")
        clear_btn = qt.QPushButton("Clear")

        for btn in (run_btn, save_btn, load_btn, clear_btn):
            btn.setMaximumHeight(24)
            toolbar_layout.addWidget(btn)
        toolbar_layout.addStretch()

        self.layout.addWidget(toolbar_widget)

        # --- Canvas (PySide2) ----------------------------------------
        # Import here so Slicer doesn't try to import PySide2 at module load
        from NodeGraph           import NodeEditorCanvas, Executor, ViewerSlotManager
        from Nodes               import ALL_NODE_CLASSES

        self._router   = ViewerSlotManager()
        # Canvas is created first; executor needs the scene from the canvas
        self._canvas   = NodeEditorCanvas(ALL_NODE_CLASSES,
                                          self._router,
                                          None)      # executor set below
        executor       = Executor(self._canvas.node_scene)
        self._router.set_executor(executor)
        self._canvas._executor = executor            # back-reference

        # PySide2 widget embedded into PythonQt layout — works in Slicer
        self.layout.addWidget(self._canvas)

        # --- Properties panel (collapsible, Slicer-native) -----------
        self._props_collapsible = ctk.ctkCollapsibleButton()
        self._props_collapsible.text      = "Node Properties"
        self._props_collapsible.collapsed = True
        self.layout.addWidget(self._props_collapsible)

        self._props_inner_layout = qt.QFormLayout(self._props_collapsible)
        self._props_inner_layout.setContentsMargins(8, 4, 8, 4)

        # Wire canvas → properties panel
        self._canvas.node_scene.node_selected.connect(self._on_node_selected)

        # Toolbar actions
        run_btn.connect("clicked()",   self._on_execute_all)
        save_btn.connect("clicked()",  self._on_save)
        load_btn.connect("clicked()",  self._on_load)
        clear_btn.connect("clicked()", self._on_clear)

    # ------------------------------------------------------------------
    # Properties panel
    # ------------------------------------------------------------------

    def _on_node_selected(self, node_item):
        self._selected_node = node_item
        self._rebuild_props_panel(node_item)

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
                def _browse(checked, line_edit=w):
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

    def _on_clear(self):
        for ni in list(self._canvas.node_scene.all_node_items()):
            self._canvas.node_scene.remove_node(ni)
        self._rebuild_props_panel(None)

    # ------------------------------------------------------------------

    def cleanup(self):
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
        from PySide2.QtCore import QPointF
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
        from PySide2.QtCore import QPointF
        scene = NodeEditorScene()
        src = scene.add_node(LoadVolumeNode(),  QPointF(0,   0))
        dst = scene.add_node(ThresholdNode(),   QPointF(0, 200))
        out_port = src.get_port('volume_out', is_input=False)
        in_port  = dst.get_port('volume_in',  is_input=True)
        edge = scene.connect_ports(out_port, in_port)
        self.assertIsNotNone(edge)
        self.delayDisplay("Edge connection OK")
