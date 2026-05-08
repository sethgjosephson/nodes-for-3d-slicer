"""
GraphExecutor - walks the DAG in topological order and calls execute() on
each node, passing upstream outputs downstream as inputs.
"""


class GraphExecutor:
    def __init__(self, graph):
        self.graph = graph

    def execute(self):
        order = self._topological_sort()
        outputs = {}  # node_id -> {port_name: vtkMRMLNode}

        for node in order:
            inputs = self._resolve_inputs(node, outputs)
            try:
                result = node.execute(inputs)
                outputs[node.id] = result or {}
            except Exception as exc:
                import slicer
                slicer.util.errorDisplay(f"Node '{node.name()}' failed:\n{exc}")
                break

    def _topological_sort(self):
        """Kahn's algorithm over all nodes in the graph."""
        all_nodes = self.graph.all_nodes()
        in_degree = {n.id: 0 for n in all_nodes}
        adjacency = {n.id: [] for n in all_nodes}
        node_map = {n.id: n for n in all_nodes}

        for node in all_nodes:
            for port in [node.output(i) for i in range(node.output_count())]:
                for connected_port in port.connected_ports():
                    downstream_id = connected_port.node().id
                    adjacency[node.id].append(downstream_id)
                    in_degree[downstream_id] += 1

        queue = [node_map[nid] for nid, deg in in_degree.items() if deg == 0]
        order = []
        while queue:
            n = queue.pop(0)
            order.append(n)
            for downstream_id in adjacency[n.id]:
                in_degree[downstream_id] -= 1
                if in_degree[downstream_id] == 0:
                    queue.append(node_map[downstream_id])

        if len(order) != len(all_nodes):
            raise RuntimeError("Graph contains a cycle — cannot execute.")

        return order

    def _resolve_inputs(self, node, outputs: dict) -> dict:
        """Collect output values from upstream nodes into this node's input dict."""
        inputs = {}
        for i, (port_name, _) in enumerate(node.INPUT_PORTS):
            port = node.input(i)
            connected = port.connected_ports()
            if not connected:
                inputs[port_name] = None
                continue
            upstream = connected[0].node()
            upstream_port_name = connected[0].name()
            upstream_outputs = outputs.get(upstream.id, {})
            inputs[port_name] = upstream_outputs.get(upstream_port_name)
        return inputs
