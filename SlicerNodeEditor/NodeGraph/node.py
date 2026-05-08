"""
SlicerBaseNode - base class for all Slicer nodes in the graph.

Every concrete node inherits this and overrides:
  - NODE_NAME, NODE_COLOR, __identifier__
  - _define_ports() to declare input/output ports
  - execute(inputs) to run the underlying Slicer operation
"""

from NodeGraphQt import BaseNode


class SlicerBaseNode(BaseNode):
    """
    Base for all nodes. Subclasses define ports and implement execute().

    Port convention:
      - Input ports carry vtkMRMLNode names (strings) pointing into slicer.mrmlScene.
      - Output ports produce new node names after execution.
    """

    __identifier__ = "slicer.nodes"
    NODE_NAME = "SlicerBaseNode"
    NODE_COLOR = (85, 100, 100)

    # Populated by subclasses: list of (name, display_name) tuples
    INPUT_PORTS = []
    OUTPUT_PORTS = []

    def __init__(self):
        super().__init__()
        self.set_color(*self.NODE_COLOR)
        self._define_ports()

    def _define_ports(self):
        for name, display in self.INPUT_PORTS:
            self.add_input(display, color=(180, 80, 80))
        for name, display in self.OUTPUT_PORTS:
            self.add_output(display, color=(80, 180, 80))

    def execute(self, inputs: dict) -> dict:
        """
        Run the Slicer operation.

        Args:
            inputs: {port_name: vtkMRMLNode or None}

        Returns:
            {port_name: vtkMRMLNode}  — outputs to pass downstream
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute()")

    def get_input_nodes(self) -> dict:
        """Resolve connected upstream nodes keyed by input port name."""
        result = {}
        for i, (name, _) in enumerate(self.INPUT_PORTS):
            port = self.input(i)
            connected = port.connected_ports()
            result[name] = connected[0].node() if connected else None
        return result
