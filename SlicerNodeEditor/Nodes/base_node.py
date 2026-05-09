"""
SlicerBaseNode — pure-Python base class for all pipeline nodes.

NodeItem (QGraphicsObject) wraps this for canvas representation.
Subclasses declare ports and properties as class attributes, then
implement execute() and optionally route_to_viewer().
"""

# ---------------------------------------------------------------------------
# Port data-type string constants
# ---------------------------------------------------------------------------
VOLUME        = "volume"
LABELMAP      = "labelmap"
SEGMENTATION  = "segmentation"
TRANSFORM     = "transform"
MODEL         = "model"
ANY           = "any"


class SlicerBaseNode:
    """
    Base for every node in the pipeline.

    Class attributes subclasses should override
    ─────────────────────────────────────────────
    NODE_NAME   : str   display name on the canvas
    CATEGORY    : str   groups the node in the Tab search menu
    NODE_COLOR  : (R,G,B)  overrides the category title-bar colour if set

    INPUT_PORTS / OUTPUT_PORTS
        list of (port_name: str, display_label: str, data_type: str)
        data_type should be one of the constants above (VOLUME, etc.)

    PROPERTIES
        list of dicts describing editable parameters:
        {
          'name':    str,           unique key
          'label':   str,           shown in properties panel
          'type':    'float'|'int'|'str'|'enum'|'bool',
          'default': value,
          # optional:
          'min': float,  'max': float,   # for float/int
          'items': [str, ...],            # for enum
        }
    """

    NODE_NAME    = "Base Node"
    CATEGORY     = "Utilities"
    NODE_COLOR   = None           # None → use CAT_COLOR[CATEGORY]

    INPUT_PORTS  = []
    OUTPUT_PORTS = []
    PROPERTIES   = []

    # Optional: name of a Slicer module whose widget should be shown in the
    # left panel when this node is selected (e.g. 'VolumeRendering',
    # 'SegmentEditor').  When set, Slicer auto-switches to that module
    # and `configure_module_widget` is called to point it at this node's
    # data.  When None (default), the standard PROPERTIES form is built
    # in the Node Editor's own properties panel.
    LINKED_MODULE = None

    # ------------------------------------------------------------------

    def __init__(self):
        self._props   = {p['name']: p['default'] for p in self.PROPERTIES}
        self._cache   = {}        # port_name → vtkMRMLNode  (output cache)
        self.is_dirty = True      # True → needs re-execution

    # ------------------------------------------------------------------
    # Property access
    # ------------------------------------------------------------------

    def get_property(self, name):
        return self._props.get(name)

    def set_property(self, name, value):
        """Update a parameter value.  Caller is responsible for dirty propagation."""
        self._props[name] = value
        self.is_dirty = True

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    def execute(self, inputs: dict) -> dict:
        """
        Run the Slicer operation.

        Parameters
        ----------
        inputs : dict
            {port_name: vtkMRMLNode | None}  — upstream outputs keyed by
            this node's input port name.

        Returns
        -------
        dict
            {port_name: vtkMRMLNode}  — outputs, one entry per OUTPUT_PORT.
            The Executor stores these into self._cache automatically.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute(inputs)")

    # ------------------------------------------------------------------
    # Viewer routing  (override in concrete nodes)
    # ------------------------------------------------------------------

    def route_to_viewer(self):
        """
        Apply this node's cached output to Slicer's viewer.
        Default is a no-op; subclasses override to change layout/routing.
        """
        pass

    # ------------------------------------------------------------------
    # Custom properties widget (optional)
    # ------------------------------------------------------------------

    def build_properties_widget(self, parent, node_item):
        """
        Optional hook: return a fully-built QWidget to embed in the
        properties panel.  Return None (default) to fall back to the
        auto-generated PROPERTIES form.

        Most nodes should use LINKED_MODULE instead — set that to the
        name of a Slicer module and Slicer's own widget for that module
        will be shown in the left panel.  This hook is for nodes that
        want a fully bespoke widget.
        """
        return None

    def configure_module_widget(self, module_widget, node_item):
        """
        Called after Slicer switches to LINKED_MODULE.  Override to
        point the module widget at this node's data — typically by
        calling its `setMRMLVolumeNode(...)` / `setSegmentationNode(...)`
        / similar setter with the value cached on this node.
        """
        pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_cached_output(self, port_name):
        return self._cache.get(port_name)

    def _get_or_create_output(self, port_name, name_hint):
        """Return cached output MRML node or create a fresh one."""
        import slicer
        existing = self._cache.get(port_name)
        if existing and slicer.mrmlScene.GetNodeByID(existing.GetID()):
            return existing
        new_node = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
        new_node.SetName(name_hint)
        new_node.CreateDefaultDisplayNodes()
        return new_node

    def mark_dirty(self):
        self.is_dirty = True

    def mark_clean(self):
        self.is_dirty = False

    def __repr__(self):
        return f"<{self.__class__.__name__} dirty={self.is_dirty}>"
