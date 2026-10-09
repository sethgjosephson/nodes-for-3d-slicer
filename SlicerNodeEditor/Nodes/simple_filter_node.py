"""
SimpleFilterNode: one node, a curated set of single-input SimpleITK
filters.

Each entry in FILTERS declares its display name, output-name suffix,
parameter definitions, and a callable that runs the filter. The node's
properties panel is a custom widget: a filter dropdown plus a form that
rebuilds to show only the selected filter's parameters.

Adding a filter = adding one FILTERS entry. Parameter names must be
unique across ALL filters (prefix them) because every parameter lives in
the node's single _props dict; that keeps values for inactive filters
alive across switches, and saved graphs restore them for free.
"""

import slicer
import sitkUtils
import SimpleITK as sitk

from .base_node import SlicerBaseNode, VOLUME


def _kernel3(value):
    """Integer radius → the 3-vector SimpleITK kernel APIs expect."""
    v = int(value)
    return [v, v, v]


def _n4_correct(img, p):
    """N4 bias correction with the standard Otsu foreground mask."""
    mask = sitk.OtsuThreshold(img, 0, 1, 200)
    return sitk.N4BiasFieldCorrection(img, mask)


# Curated filter registry. 'call' receives (image, get_property).
# 'cast_float': filter requires a real-valued input image.
# 'auto': False keeps slow filters out of the live auto-rerun loop.
FILTERS = {
    'Gradient Magnitude': {
        'suffix': 'gradmag', 'cast_float': False, 'auto': True,
        'params': [],
        'call': lambda img, p: sitk.GradientMagnitude(img),
    },
    'Sobel Edge Detection': {
        'suffix': 'sobel', 'cast_float': True, 'auto': True,
        'params': [],
        'call': lambda img, p: sitk.SobelEdgeDetection(img),
    },
    'Canny Edge Detection': {
        'suffix': 'canny', 'cast_float': True, 'auto': True,
        'params': [
            {'name': 'canny_lower', 'label': 'Lower Threshold',
             'type': 'float', 'default': 10.0, 'min': 0.0, 'max': 5000.0},
            {'name': 'canny_upper', 'label': 'Upper Threshold',
             'type': 'float', 'default': 50.0, 'min': 0.0, 'max': 5000.0},
            {'name': 'canny_variance', 'label': 'Variance',
             'type': 'float', 'default': 1.0, 'min': 0.0, 'max': 50.0},
        ],
        'call': lambda img, p: sitk.CannyEdgeDetection(
            img,
            lowerThreshold=float(p('canny_lower')),
            upperThreshold=float(p('canny_upper')),
            variance=[float(p('canny_variance'))] * 3),
    },
    'Laplacian Sharpening': {
        'suffix': 'sharp', 'cast_float': False, 'auto': True,
        'params': [],
        'call': lambda img, p: sitk.LaplacianSharpening(img),
    },
    'Curvature Flow Denoise': {
        'suffix': 'cflow', 'cast_float': True, 'auto': True,
        'params': [
            {'name': 'cf_timestep', 'label': 'Time Step',
             'type': 'float', 'default': 0.0625, 'min': 0.001, 'max': 0.25},
            {'name': 'cf_iterations', 'label': 'Iterations',
             'type': 'int', 'default': 5, 'min': 1, 'max': 50},
        ],
        'call': lambda img, p: sitk.CurvatureFlow(
            img,
            timeStep=float(p('cf_timestep')),
            numberOfIterations=int(p('cf_iterations'))),
    },
    'Anisotropic Diffusion': {
        'suffix': 'aniso', 'cast_float': True, 'auto': True,
        'params': [
            # 3D stability requires timeStep <= 0.0625.
            {'name': 'ad_timestep', 'label': 'Time Step',
             'type': 'float', 'default': 0.06, 'min': 0.001, 'max': 0.0625},
            {'name': 'ad_conductance', 'label': 'Conductance',
             'type': 'float', 'default': 3.0, 'min': 0.1, 'max': 10.0},
            {'name': 'ad_iterations', 'label': 'Iterations',
             'type': 'int', 'default': 5, 'min': 1, 'max': 50},
        ],
        'call': lambda img, p: sitk.GradientAnisotropicDiffusion(
            img,
            timeStep=float(p('ad_timestep')),
            conductanceParameter=float(p('ad_conductance')),
            numberOfIterations=int(p('ad_iterations'))),
    },
    'Grayscale Fill Hole': {
        'suffix': 'fillhole', 'cast_float': False, 'auto': True,
        'params': [],
        'call': lambda img, p: sitk.GrayscaleFillhole(img),
    },
    'Grayscale Grind Peak': {
        'suffix': 'grindpeak', 'cast_float': False, 'auto': True,
        'params': [],
        'call': lambda img, p: sitk.GrayscaleGrindPeak(img),
    },
    'Morphological Opening': {
        'suffix': 'open', 'cast_float': False, 'auto': True,
        'params': [
            {'name': 'mo_radius', 'label': 'Radius (vox)',
             'type': 'int', 'default': 1, 'min': 1, 'max': 10},
        ],
        'call': lambda img, p: sitk.GrayscaleMorphologicalOpening(
            img, _kernel3(p('mo_radius'))),
    },
    'Morphological Closing': {
        'suffix': 'close', 'cast_float': False, 'auto': True,
        'params': [
            {'name': 'mc_radius', 'label': 'Radius (vox)',
             'type': 'int', 'default': 1, 'min': 1, 'max': 10},
        ],
        'call': lambda img, p: sitk.GrayscaleMorphologicalClosing(
            img, _kernel3(p('mc_radius'))),
    },
    'Invert Intensity': {
        'suffix': 'invert', 'cast_float': False, 'auto': True,
        'params': [
            {'name': 'inv_maximum', 'label': 'Maximum',
             'type': 'float', 'default': 255.0, 'min': 1.0, 'max': 65535.0},
        ],
        'call': lambda img, p: sitk.InvertIntensity(
            img, maximum=float(p('inv_maximum'))),
    },
    'Rescale Intensity': {
        'suffix': 'rescale', 'cast_float': False, 'auto': True,
        'params': [
            {'name': 'rs_min', 'label': 'Output Min',
             'type': 'float', 'default': 0.0, 'min': -32768.0, 'max': 65535.0},
            {'name': 'rs_max', 'label': 'Output Max',
             'type': 'float', 'default': 255.0, 'min': -32768.0, 'max': 65535.0},
        ],
        'call': lambda img, p: sitk.RescaleIntensity(
            img,
            outputMinimum=float(p('rs_min')),
            outputMaximum=float(p('rs_max'))),
    },
    'Sigmoid Contrast': {
        'suffix': 'sigmoid', 'cast_float': False, 'auto': True,
        'params': [
            {'name': 'sig_alpha', 'label': 'Alpha (width)',
             'type': 'float', 'default': 50.0, 'min': -1000.0, 'max': 1000.0},
            {'name': 'sig_beta', 'label': 'Beta (center)',
             'type': 'float', 'default': 100.0, 'min': -2000.0, 'max': 5000.0},
        ],
        'call': lambda img, p: sitk.Sigmoid(
            img,
            alpha=float(p('sig_alpha')),
            beta=float(p('sig_beta')),
            outputMaximum=255.0, outputMinimum=0.0),
    },
    'N4 Bias Field Correction': {
        # Takes tens of seconds on full-size volumes: manual re-run only.
        'suffix': 'n4', 'cast_float': True, 'auto': False,
        'params': [],
        'call': _n4_correct,
    },
}


class SimpleFilterNode(SlicerBaseNode):
    NODE_NAME = "Simple Filter"
    CATEGORY  = "Filters"

    INPUT_PORTS  = [("volume_in",  "Volume", VOLUME)]
    OUTPUT_PORTS = [("volume_out", "Volume", VOLUME)]

    # Union of the filter selector and every filter's parameters, so the
    # base class seeds _props with defaults for all of them and saved
    # graphs round-trip every value. The custom widget below shows only
    # the ACTIVE filter's parameters.
    PROPERTIES = ([{'name': 'filter', 'label': 'Filter', 'type': 'enum',
                    'default': 'Gradient Magnitude',
                    'items': list(FILTERS.keys())}]
                  + [dict(param)
                     for spec in FILTERS.values()
                     for param in spec['params']])

    def __init__(self):
        super().__init__()
        self._sync_auto_execute()

    # ------------------------------------------------------------------

    def set_property(self, name, value):
        SlicerBaseNode.set_property(self, name, value)
        if name == 'filter':
            self._sync_auto_execute()

    def _sync_auto_execute(self):
        """Instance attribute shadows the class default so expensive
        filters (N4) stay out of the live auto-rerun loop while cheap
        ones keep updating live."""
        spec = FILTERS.get(self.get_property('filter'))
        self.AUTO_EXECUTE = bool(spec.get('auto', True)) if spec else True

    # ------------------------------------------------------------------

    def execute(self, inputs):
        node = inputs.get('volume_in')
        if node is None:
            raise ValueError("Simple Filter: no input volume connected.")

        name = self.get_property('filter')
        spec = FILTERS.get(name)
        if spec is None:
            raise ValueError(f"Simple Filter: unknown filter '{name}'.")

        img = sitkUtils.PullVolumeFromSlicer(node)
        if spec.get('cast_float'):
            img = sitk.Cast(img, sitk.sitkFloat32)
        result = spec['call'](img, self.get_property)

        out = self._get_or_create_output(
            'volume_out', node.GetName() + '_' + spec['suffix'])
        sitkUtils.PushVolumeToSlicer(result, out)
        return {'volume_out': out}

    def route_to_viewer(self):
        node = self._cache.get('volume_out')
        if node:
            from .io_nodes import _route_volume_to_slices
            _route_volume_to_slices(node)

    # ------------------------------------------------------------------
    # Custom properties widget: filter dropdown + per-filter form
    # ------------------------------------------------------------------

    def build_properties_widget(self, parent, node_item):
        import qt

        container = qt.QWidget(parent)
        layout = qt.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        combo = qt.QComboBox()
        names = list(FILTERS.keys())
        for name in names:
            combo.addItem(name)
        current = self.get_property('filter')
        if current in names:
            combo.setCurrentIndex(names.index(current))
        layout.addWidget(combo)

        params_host   = qt.QWidget()
        params_layout = qt.QFormLayout(params_host)
        params_layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(params_host)

        def _clear_params():
            while params_layout.count():
                item = params_layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        def _build_params():
            _clear_params()
            spec = FILTERS.get(self.get_property('filter'))
            if spec is None:
                return
            for prop in spec['params']:
                w = self._make_param_widget(prop, node_item)
                if w is not None:
                    params_layout.addRow(qt.QLabel(prop['label'] + ":"), w)

        def _on_filter_changed(text):
            node_item.set_property('filter', text)
            _build_params()

        combo.connect('currentTextChanged(const QString&)',
                      _on_filter_changed)
        _build_params()
        return container

    @staticmethod
    def _make_param_widget(prop, node_item):
        import qt
        current = node_item.node_data.get_property(prop['name'])

        if prop['type'] == 'float':
            w = qt.QDoubleSpinBox()
            w.setMinimum(prop.get('min', -1e9))
            w.setMaximum(prop.get('max',  1e9))
            w.setSingleStep(0.1)
            w.setDecimals(4)
            w.setValue(float(current))
            w.connect('valueChanged(double)',
                      lambda v, n=prop['name'], ni=node_item:
                          ni.set_property(n, v))
            return w

        if prop['type'] == 'int':
            w = qt.QSpinBox()
            w.setMinimum(int(prop.get('min', -999999)))
            w.setMaximum(int(prop.get('max',  999999)))
            w.setValue(int(current))
            w.connect('valueChanged(int)',
                      lambda v, n=prop['name'], ni=node_item:
                          ni.set_property(n, v))
            return w

        return None
