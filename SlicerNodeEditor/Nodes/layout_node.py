"""
Layout node — routes up to four inputs to Slicer's four views at once.

Pressing 1 or 2 on this node switches Slicer to the Four-Up layout and
pipes each connected volume to the corresponding slice/3D view.

Inputs
------
red_in    → Red slice background
yellow_in → Yellow slice background
green_in  → Green slice background
render_in → 3D view (volume rendering, optional)
"""

import slicer
from .base_node import SlicerBaseNode, VOLUME


class LayoutNode(SlicerBaseNode):
    NODE_NAME    = "Layout"
    CATEGORY     = "Layout"
    NODE_COLOR   = (72, 72, 72)

    INPUT_PORTS  = [
        ("red_in",    "Red Slice",    VOLUME),
        ("yellow_in", "Yellow Slice", VOLUME),
        ("green_in",  "Green Slice",  VOLUME),
        ("render_in", "3D Render",    VOLUME),
    ]
    OUTPUT_PORTS = []

    PROPERTIES = [
        {'name': 'layout', 'label': 'Slicer Layout', 'type': 'enum',
         'default': 'Four Up',
         'items': ['Four Up', 'Conventional', 'Three Over Three',
                   'Side By Side', '3D Only']},
    ]

    _LAYOUT_MAP = None  # populated lazily at first use

    @classmethod
    def _get_layout_map(cls):
        if cls._LAYOUT_MAP is None:
            cls._LAYOUT_MAP = {
                'Four Up':          slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView,
                'Conventional':     slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView,
                'Three Over Three': slicer.vtkMRMLLayoutNode.SlicerLayoutThreeOverThreeView,
                'Side By Side':     slicer.vtkMRMLLayoutNode.SlicerLayoutSideBySideView,
                '3D Only':          slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView,
            }
        return cls._LAYOUT_MAP

    def execute(self, inputs):
        # Store inputs so route_to_viewer can use them even if called later
        self._cache['_red']    = inputs.get('red_in')
        self._cache['_yellow'] = inputs.get('yellow_in')
        self._cache['_green']  = inputs.get('green_in')
        self._cache['_render'] = inputs.get('render_in')
        return {}

    def route_to_viewer(self):
        layout_name = self.get_property('layout')
        layout_id   = self._get_layout_map().get(
            layout_name,
            slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)

        lm = slicer.app.layoutManager()
        lm.setLayout(layout_id)

        # Route slices
        mapping = {
            'Red':    self._cache.get('_red'),
            'Yellow': self._cache.get('_yellow'),
            'Green':  self._cache.get('_green'),
        }
        for color, vol in mapping.items():
            cn = slicer.mrmlScene.GetNodeByID(
                f'vtkMRMLSliceCompositeNode{color}')
            if cn and vol is not None:
                cn.SetBackgroundVolumeID(vol.GetID())

        slicer.util.resetSliceViews()

        # Volume rendering for 3D view
        render_vol = self._cache.get('_render')
        if render_vol is not None:
            vr_logic = slicer.modules.volumerendering.logic()
            vr_logic.SetDefaultVolumeRenderingProperties(render_vol)
            dn = vr_logic.GetFirstVolumeRenderingDisplayNode(render_vol)
            if dn is None:
                dn = vr_logic.CreateDefaultVolumeRenderingDisplayNode(render_vol)
                render_vol.AddAndObserveDisplayNodeID(dn.GetID())
            dn.SetVisibility(True)
