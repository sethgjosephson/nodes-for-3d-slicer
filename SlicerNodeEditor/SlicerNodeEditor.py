"""
SlicerNodeEditor - Nuke-style node graph interface for 3D Slicer.

Entry point for the Slicer scripted module. The Widget embeds the NodeGraphQt
canvas and wires it to Slicer's MRML scene and CLI modules.
"""

import os
import sys

import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleWidget,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleTest,
)
from slicer.util import VTKObservationMixin


class SlicerNodeEditor(ScriptedLoadableModule):
    def __init__(self, parent):
        super().__init__(parent)
        parent.title = "Node Editor"
        parent.categories = ["Utilities"]
        parent.dependencies = []
        parent.contributors = ["Seth Rivers"]
        parent.helpText = (
            "A Nuke-style node graph interface for 3D Slicer. "
            "Wire together I/O, filter, segmentation, registration, and "
            "visualization nodes to build non-destructive processing pipelines."
        )
        parent.acknowledgementText = ""
        parent.icon = self._iconPath()

    def _iconPath(self):
        import qt
        iconPath = os.path.join(os.path.dirname(__file__), "Resources", "Icons", "SlicerNodeEditor.png")
        if os.path.isfile(iconPath):
            return qt.QIcon(iconPath)
        return qt.QIcon()


class SlicerNodeEditorWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        self.logic = None
        self._graphWidget = None

    def setup(self):
        super().setup()
        self.logic = SlicerNodeEditorLogic()
        self._ensureDependencies()
        self._buildUI()

    def _ensureDependencies(self):
        """Install NodeGraphQt into Slicer's Python environment on first run."""
        try:
            import NodeGraphQt  # noqa: F401
        except ImportError:
            slicer.util.pip_install("NodeGraphQt")

    def _buildUI(self):
        from PySide2 import QtWidgets, QtCore
        from NodeGraph.canvas import NodeEditorCanvas

        # Wrap PySide2 widget in a Qt (slicer qt module) container
        import qt
        container = qt.QWidget()
        container.setLayout(qt.QVBoxLayout())
        container.layout().setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = qt.QHBoxLayout()
        executeBtn = qt.QPushButton("Execute Graph")
        executeBtn.setToolTip("Run all nodes in dependency order")
        executeBtn.connect("clicked()", self._onExecute)

        clearBtn = qt.QPushButton("Clear")
        clearBtn.connect("clicked()", self._onClear)

        saveBtn = qt.QPushButton("Save Graph")
        saveBtn.connect("clicked()", self._onSaveGraph)

        loadBtn = qt.QPushButton("Load Graph")
        loadBtn.connect("clicked()", self._onLoadGraph)

        toolbar.addWidget(executeBtn)
        toolbar.addWidget(clearBtn)
        toolbar.addStretch()
        toolbar.addWidget(saveBtn)
        toolbar.addWidget(loadBtn)

        toolbarWidget = qt.QWidget()
        toolbarWidget.setLayout(toolbar)
        container.layout().addWidget(toolbarWidget)

        # Node graph canvas (PySide2-based NodeGraphQt)
        self._graphWidget = NodeEditorCanvas()
        # Embed PySide2 widget into the Qt container via QWidget.createWindowContainer
        pysideWrapper = qt.QWidget.createWindowContainer(
            self._graphWidget.get_native_window(), container
        )
        container.layout().addWidget(pysideWrapper)

        self.layout.addWidget(container)

    def _onExecute(self):
        if self._graphWidget:
            from NodeGraph.executor import GraphExecutor
            executor = GraphExecutor(self._graphWidget.graph)
            executor.execute()

    def _onClear(self):
        if self._graphWidget:
            self._graphWidget.graph.clear_session()

    def _onSaveGraph(self):
        import qt
        path = qt.QFileDialog.getSaveFileName(None, "Save Node Graph", "", "JSON (*.json)")[0]
        if path and self._graphWidget:
            self._graphWidget.graph.save_session(path)

    def _onLoadGraph(self):
        import qt
        path = qt.QFileDialog.getOpenFileName(None, "Load Node Graph", "", "JSON (*.json)")[0]
        if path and self._graphWidget:
            self._graphWidget.graph.load_session(path)

    def cleanup(self):
        self.removeObservers()


class SlicerNodeEditorLogic(ScriptedLoadableModuleLogic):
    pass


class SlicerNodeEditorTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear()

    def runTest(self):
        self.setUp()
        self.test_GraphCreation()

    def test_GraphCreation(self):
        self.delayDisplay("Testing node graph creation")
        from NodeGraph.canvas import NodeEditorCanvas
        canvas = NodeEditorCanvas()
        self.assertIsNotNone(canvas)
        self.delayDisplay("Node graph creation test passed")
