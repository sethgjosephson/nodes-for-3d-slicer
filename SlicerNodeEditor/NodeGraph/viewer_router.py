"""
ViewerSlotManager — manages the two viewer slots (keys 1 and 2).

Pressing 1 or 2 over a node assigns that node to the slot *and* activates
it.  Pressing the same key again with nothing hovered recalls the last
assignment for that slot (toggle-style, like Nuke).
"""


class ViewerSlotManager:
    """
    Slot registry + Slicer view routing.

    Usage
    -----
    router = ViewerSlotManager()

    # User presses '1' while hovering NodeItem 'n'
    router.assign_and_activate(n, 1)

    # User presses '1' again with nothing hovered
    router.activate(1)
    """

    def __init__(self, executor=None):
        self._slots    = {1: None, 2: None}   # slot → NodeItem
        self._active   = 1
        self._executor = executor              # set after creation

    def set_executor(self, executor):
        self._executor = executor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign_and_activate(self, node_item, slot: int):
        """Assign node_item to slot and immediately display it."""
        self._slots[slot] = node_item
        self._active      = slot
        self._display(node_item)

    def activate(self, slot: int):
        """Re-display the node already in this slot (no reassignment)."""
        self._active = slot
        node_item    = self._slots.get(slot)
        if node_item is not None:
            self._display(node_item)

    def get_slot_node(self, slot: int):
        return self._slots.get(slot)

    def get_active_slot(self):
        return self._active

    def clear_node(self, node_item):
        """Remove a node from whichever slot it occupies (called on delete)."""
        for slot, item in list(self._slots.items()):
            if item is node_item:
                self._slots[slot] = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _display(self, node_item):
        """Execute up to this node (lazy) then route Slicer's viewer."""
        if self._executor is not None:
            try:
                self._executor.execute_up_to(node_item)
            except Exception as exc:
                import slicer
                slicer.util.errorDisplay(
                    f"Execution failed before routing viewer:\n{exc}")
                return

        try:
            node_item.node_data.route_to_viewer()
        except Exception as exc:
            import slicer
            slicer.util.errorDisplay(
                f"Viewer routing failed for '{node_item.node_data.NODE_NAME}':\n{exc}")
