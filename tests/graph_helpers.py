"""
Helpers for workflow tests that drive the live Node Editor canvas.

Every helper works on the module's own scene, executor and viewer slots, so a test exercises the same path as a person pressing keys on the canvas.
"""

import json
import os
import time

import slicer

__all__ = ['G', 'check', 'section', 'wait', 'screenshot', 'OUT_DIR',
           'array', 'mrml_exists']

OUT_DIR = os.environ.get('NODE_EDITOR_OUT_DIR') or os.path.dirname(
    os.environ.get('NODE_EDITOR_OUT', '.'))

_failures = []


def section(title):
    print(f"\n=== {title} ===")


def check(condition, message):
    """Record a check. Failures are collected and raised by G.finish()."""
    if condition:
        print(f"  ok    {message}")
    else:
        print(f"  FAIL  {message}")
        _failures.append(message)
    return bool(condition)


def wait(ms=200):
    """Let the Qt event loop run for `ms` milliseconds."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        slicer.app.processEvents()
        time.sleep(0.01)
    slicer.app.processEvents()


def screenshot(name):
    """Save the main window to OUT_DIR/name.png."""
    slicer.app.processEvents()
    slicer.util.forceRenderAllViews()
    slicer.app.processEvents()
    path = os.path.join(OUT_DIR, name + '.png')
    slicer.util.mainWindow().grab().save(path)
    print(f"  shot  {path}")
    return path


def array(volume):
    return slicer.util.arrayFromVolume(volume)


def mrml_exists(node):
    return (node is not None
            and slicer.mrmlScene.GetNodeByID(node.GetID()) is not None)


class G:
    """A handle on the live editor graph."""

    def __init__(self, editor):
        self.editor = editor
        self.canvas = editor._canvas
        self.scene = editor._canvas.node_scene
        self.router = editor._router
        self._row = 0

    # -- building ------------------------------------------------------

    def clear(self):
        self.editor._clear_graph()
        self._row = 0

    def add(self, type_name, x=None, y=None, **props):
        from Nodes import NODE_TYPE_REGISTRY
        from NodeGraph._qt import QPointF
        cls = NODE_TYPE_REGISTRY[type_name]
        if x is None:
            x = 0
        if y is None:
            y = self._row * 140
            self._row += 1
        item = self.scene.add_node(cls(), QPointF(x, y))
        for key, value in props.items():
            self.set(item, key, value)
        return item

    def set(self, item, name, value):
        if name not in item.node_data._props:
            raise KeyError(f"{item.node_data.NODE_NAME} has no property "
                           f"'{name}'")
        # The same call the properties panel makes.
        item.set_property(name, value)

    def connect(self, src, src_port, dst, dst_port):
        out_port = src.get_port(src_port, is_input=False)
        in_port = dst.get_port(dst_port, is_input=True)
        if out_port is None:
            raise KeyError(f"{src.node_data.NODE_NAME} has no output "
                           f"'{src_port}'")
        if in_port is None:
            raise KeyError(f"{dst.node_data.NODE_NAME} has no input "
                           f"'{dst_port}'")
        edge = self.scene.connect_ports(out_port, in_port)
        if edge is None:
            raise RuntimeError(
                f"connection refused: {src.node_data.NODE_NAME}.{src_port}"
                f" -> {dst.node_data.NODE_NAME}.{dst_port}")
        return edge

    def chain(self, *items):
        """Connect each item to the next through their first ports that the scene's auto-connect accepts."""
        for a, b in zip(items, items[1:]):
            if not self.scene.try_auto_connect(a, b):
                raise RuntimeError(
                    f"auto-connect refused: {a.node_data.NODE_NAME} -> "
                    f"{b.node_data.NODE_NAME}")

    # -- keys ----------------------------------------------------------

    def select(self, *items):
        self.scene.clearSelection()
        for item in items:
            item.setSelected(True)
        slicer.app.processEvents()

    def press(self, key, ctrl=False, timeout_s=600):
        """Send a key press to the canvas, as typed with the cursor over it.
        `key` is a character such as '1', 'D', 'F' or a qt.Qt.Key."""
        import qt
        if isinstance(key, str):
            names = {'Del': qt.Qt.Key_Delete, 'Esc': qt.Qt.Key_Escape,
                     'Tab': qt.Qt.Key_Tab}
            code = names.get(key)
            if code is None:
                code = getattr(qt.Qt, 'Key_' + key.upper())
        else:
            code = key
        mods = qt.Qt.ControlModifier if ctrl else qt.Qt.NoModifier
        event = qt.QKeyEvent(qt.QEvent.KeyPress, code, mods)
        self.canvas.keyPressEvent(event)
        wait(400)
        self.wait_async(timeout_s)
        wait(100)

    # -- running -------------------------------------------------------

    def view(self, item, slot=1, timeout_s=600):
        """Press a viewer key on a node, then wait for async nodes."""
        self.router.assign_and_activate(item, slot)
        self.wait_async(timeout_s)
        wait(150)

    def wait_async(self, timeout_s=600):
        end = time.time() + timeout_s
        while time.time() < end:
            pending = [ni for ni in self.scene.all_node_items()
                       if getattr(ni.node_data, '_async_pending', False)]
            if not pending:
                return True
            wait(250)
        raise TimeoutError("async nodes still running after "
                           f"{timeout_s} s")

    def out(self, item, port):
        return item.node_data.get_cached_output(port)

    def error(self, item):
        return item.node_data._last_error

    def dirty(self):
        return [ni.node_data.NODE_NAME for ni in self.scene.all_node_items()
                if ni.node_data.is_dirty]

    def errors(self):
        return {ni.node_data.NODE_NAME: ni.node_data._last_error
                for ni in self.scene.all_node_items()
                if ni.node_data._last_error}

    # -- files ---------------------------------------------------------

    def save(self, path):
        with open(path, 'w') as f:
            json.dump(self.scene.serialise(), f, indent=2)
        return path

    def load(self, path):
        with open(path) as f:
            data = json.load(f)
        self.editor._clear_graph()
        self.scene.deserialise(data, self.router)
        return self.scene.all_node_items()

    def by_name(self, node_name, index=0):
        found = [ni for ni in self.scene.all_node_items()
                 if ni.node_data.NODE_NAME == node_name]
        return found[index]

    # -- verdict -------------------------------------------------------

    @staticmethod
    def finish():
        if _failures:
            raise AssertionError(
                f"{len(_failures)} check(s) failed:\n  - "
                + "\n  - ".join(_failures))
        print("all checks passed")
