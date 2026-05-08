set(MODULE_NAME SlicerNodeEditor)
set(MODULE_TITLE "Node Editor")

set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  NodeGraph/__init__.py
  NodeGraph/canvas.py
  NodeGraph/node.py
  NodeGraph/port.py
  NodeGraph/edge.py
  NodeGraph/executor.py
  Nodes/__init__.py
  Nodes/base_node.py
  Nodes/io_nodes.py
  Nodes/filter_nodes.py
  Nodes/segment_nodes.py
  Nodes/register_nodes.py
  Nodes/viz_nodes.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  )

slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )
