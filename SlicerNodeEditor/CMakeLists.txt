set(MODULE_NAME SlicerNodeEditor)
set(MODULE_TITLE "Node Editor")

set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  NodeGraph/__init__.py
  NodeGraph/_qt.py
  NodeGraph/constants.py
  NodeGraph/canvas.py
  NodeGraph/scene.py
  NodeGraph/node_item.py
  NodeGraph/port_item.py
  NodeGraph/edge_item.py
  NodeGraph/search_popup.py
  NodeGraph/viewer_router.py
  NodeGraph/executor.py
  Nodes/__init__.py
  Nodes/base_node.py
  Nodes/io_nodes.py
  Nodes/filter_nodes.py
  Nodes/segment_nodes.py
  Nodes/register_nodes.py
  Nodes/viz_nodes.py
  Nodes/layout_node.py
  Nodes/process_nodes.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/demo_workflow.json
  )

slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )
