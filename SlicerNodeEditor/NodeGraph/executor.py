"""
Executor — dirty-flag-aware lazy pipeline executor.

Only nodes that are dirty (and their dirty ancestors) are re-executed
when a viewer slot is activated.  Clean nodes reuse their cached outputs.
"""


class Executor:
    """
    Walks the scene graph and executes dirty nodes in topological order
    up to and including a target node.

    Parameters
    ----------
    scene : NodeEditorScene
        Provides topology queries (get_incoming_edge, get_outgoing_edges,
        all_nodes).
    """

    def __init__(self, scene):
        self._scene = scene

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def execute_up_to(self, target_node_item):
        """
        Execute all dirty ancestors of target_node_item, then
        target_node_item itself if dirty.

        Raises RuntimeError if the graph contains a cycle.
        """
        ancestors = self._ancestors_including(target_node_item)
        order     = self._topological_sort(ancestors)

        for node_item in order:
            if node_item.node_data.is_dirty:
                self._run_node(node_item)

    def execute_all(self):
        """Execute every dirty node in the scene (full pipeline run)."""
        try:
            order = self._topological_sort(set(self._scene.all_node_items()))
        except RuntimeError:
            raise
        for node_item in order:
            if node_item.node_data.is_dirty:
                self._run_node(node_item)

    # ------------------------------------------------------------------
    # Internal — graph traversal
    # ------------------------------------------------------------------

    def _ancestors_including(self, node_item):
        """Return {node_item} ∪ all transitive upstream nodes."""
        visited = set()
        stack   = [node_item]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for edge in self._scene.get_incoming_edges(current):
                stack.append(edge.source_port.node_item)
        return visited

    def _topological_sort(self, node_set):
        """Kahn's algorithm restricted to node_set."""
        # Build adjacency within the set
        in_degree  = {n: 0 for n in node_set}
        downstream = {n: [] for n in node_set}

        for node in node_set:
            for edge in self._scene.get_outgoing_edges(node):
                child = edge.target_port.node_item
                if child in node_set:
                    downstream[node].append(child)
                    in_degree[child] += 1

        queue  = [n for n, d in in_degree.items() if d == 0]
        result = []

        while queue:
            n = queue.pop(0)
            result.append(n)
            for child in downstream[n]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(result) != len(node_set):
            raise RuntimeError(
                "Node graph contains a cycle — cannot execute.")

        return result

    # ------------------------------------------------------------------
    # Internal — single node execution
    # ------------------------------------------------------------------

    @staticmethod
    def _passthrough(node_data, inputs):
        """
        For each OUTPUT_PORT, find the first INPUT_PORT with a
        type-compatible value and forward it through.  Used when a
        node is disabled (Nuke-style D-key) — the node becomes a
        no-op, downstream sees the unprocessed upstream data.
        """
        result = {}
        for out_name, _out_label, out_type in node_data.OUTPUT_PORTS:
            for in_name, _in_label, in_type in node_data.INPUT_PORTS:
                if (in_type == out_type
                        or in_type == 'any'
                        or out_type == 'any'):
                    val = inputs.get(in_name)
                    if val is not None:
                        result[out_name] = val
                        break
        return result

    def _run_node(self, node_item):
        """Resolve inputs from upstream caches and call node_data.execute()."""
        node_data = node_item.node_data
        inputs    = {}

        for port_name, _label, _dtype in node_data.INPUT_PORTS:
            port = node_item.get_port(port_name, is_input=True)
            edge = self._scene.get_incoming_edge(port)
            if edge is not None:
                up_node = edge.source_port.node_item
                up_name = edge.source_port.port_name
                inputs[port_name] = up_node.node_data._cache.get(up_name)
            else:
                inputs[port_name] = None

        # Wire up ModifiedEvent observers on the MRML nodes that ARE
        # the current inputs.  If any of them gets modified later (by
        # any source, in-graph or out), our debounced callback marks
        # this node dirty so the user knows to re-execute.
        try:
            node_data._refresh_input_observers(node_item)
        except Exception:
            import traceback; traceback.print_exc()

        # Stash the NodeItem so async callbacks (e.g. CLI completion
        # observers) can find their visual node back.  The reference is
        # not weak — if the user deletes the node the callback's
        # node_item.update() is a Qt no-op on a removed item.
        node_data._executing_node_item = node_item

        # Suppress our own observer callbacks for any Modified events
        # fired as a side-effect of execute() itself.
        node_data._self_modified = True
        try:
            if getattr(node_data, 'is_disabled', False):
                # Nuke-style passthrough: skip this node's work, forward
                # the first type-compatible input to each output.
                result = self._passthrough(node_data, inputs)
            else:
                result = node_data.execute(inputs)
        except Exception as exc:
            import slicer
            slicer.util.errorDisplay(
                f"Node '{node_data.NODE_NAME}' raised an error:\n{exc}")
            return
        finally:
            node_data._self_modified = False

        # Store outputs in cache and mark clean
        node_data._cache.update(result or {})
        node_data.mark_clean()
        node_item.update()   # repaint to remove dirty indicator
