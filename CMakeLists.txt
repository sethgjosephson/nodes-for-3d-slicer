cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(NodesFor3DSlicer)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/sethgjosephson/nodes-for-3d-slicer")
set(EXTENSION_CATEGORY "Utilities")
set(EXTENSION_CONTRIBUTORS "Seth Rivers")
set(EXTENSION_DESCRIPTION "A node-graph editor for 3D Slicer. Each node wraps a Slicer operation; edges carry MRML data between nodes.")
set(EXTENSION_ICONURL "")
set(EXTENSION_SCREENSHOTURLS "")
set(EXTENSION_DEPENDS "NA")

#-----------------------------------------------------------------------------
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
add_subdirectory(SlicerNodeEditor)

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
