# The canvas driven by Qt input events delivered to the widgets, the way
# the mouse and keyboard deliver them: Tab search, typing, port drags,
# node drags, double-click, wheel zoom, middle-button pan.
import qt

g = G(editor)
g.clear()
canvas = g.canvas
viewport = canvas.viewport()
app = slicer.app


def view_pos(scene_point):
    p = canvas.mapFromScene(scene_point)
    return qt.QPointF(p.x(), p.y())


def mouse(kind, scene_point, button=qt.Qt.LeftButton, buttons=None):
    if buttons is None:
        buttons = button if kind != qt.QEvent.MouseButtonRelease else qt.Qt.NoButton
    # The scene finds the item under the cursor from the screen position,
    # so the event must carry one that matches its local position.
    local = view_pos(scene_point)
    screen = viewport.mapToGlobal(qt.QPoint(int(local.x()), int(local.y())))
    ev = qt.QMouseEvent(kind, local, qt.QPointF(screen.x(), screen.y()),
                        button, buttons, qt.Qt.NoModifier)
    app.sendEvent(viewport, ev)
    app.processEvents()


def move(scene_point, buttons=qt.Qt.NoButton):
    mouse(qt.QEvent.MouseMove, scene_point, qt.Qt.NoButton, buttons)


def drag(start, end, steps=8, button=qt.Qt.LeftButton):
    move(start)
    mouse(qt.QEvent.MouseButtonPress, start, button)
    for i in range(1, steps + 1):
        t = i / float(steps)
        move(qt.QPointF(start.x() + (end.x() - start.x()) * t,
                        start.y() + (end.y() - start.y()) * t), button)
    mouse(qt.QEvent.MouseButtonRelease, end, button)
    wait(100)


def key(widget, code, text='', mods=qt.Qt.NoModifier):
    app.sendEvent(widget, qt.QKeyEvent(qt.QEvent.KeyPress, code, mods, text))
    app.sendEvent(widget, qt.QKeyEvent(qt.QEvent.KeyRelease, code, mods, text))
    app.processEvents()


def type_text(widget, text):
    for ch in text:
        code = getattr(qt.Qt, 'Key_' + ch.upper(), qt.Qt.Key_Space)
        key(widget, code, ch)


def node_center(item):
    return item.sceneBoundingRect().center()


def add_by_search(text, at):
    """Hover at a scene point, press Tab, type, press Return."""
    move(at)
    canvas.setFocus()
    key(canvas, qt.Qt.Key_Tab, '\t')
    wait(150)
    popup = canvas._popup
    if popup is None or not popup.isVisible():
        return None
    type_text(popup._search, text)
    wait(100)
    key(popup._search, qt.Qt.Key_Return, '\r')
    wait(200)
    return popup


section("Tab opens the search at the cursor")
canvas.frame_all()
before_focus = app.focusWidget()
popup = add_by_search('sample', qt.QPointF(0, 0))
check(popup is not None, "Tab opened the search popup (not eaten by focus traversal)")
items = g.scene.all_node_items()
check(len(items) == 1 and items[0].node_data.NODE_NAME == 'Sample Data',
      f"typing 'sample' and Return added Sample Data "
      f"({[i.node_data.NODE_NAME for i in items]})")
src = items[0] if items else None
c = node_center(src)
check(abs(c.x()) < 5 and abs(c.y()) < 5,
      f"the node is centered where the cursor was ({c.x():.0f}, {c.y():.0f})")
check(src.isSelected(), "the new node is selected")
check(not popup.isVisible(), "the popup closed")

section("a second node auto-connects to the selected one")
add_by_search('gauss', qt.QPointF(0, 160))
names = [i.node_data.NODE_NAME for i in g.scene.all_node_items()]
check(names == ['Sample Data', 'Gaussian Smooth'], f"nodes: {names}")
check(len(g.scene._edges) == 1, "auto-connected with one edge")
smooth = g.by_name('Gaussian Smooth')

section("filtering the search list")
move(qt.QPointF(300, 0))
key(canvas, qt.Qt.Key_Tab, '\t')
wait(150)
popup = canvas._popup
type_text(popup._search, 'seg')
wait(100)
listed = [popup._list.item(i).text().strip() for i in range(popup._list.count)]
print(f"  'seg' lists: {listed}")
check('Segmentation' in listed and 'Segment Statistics' in listed
      and 'Gaussian Smooth' not in listed, "the list is filtered by the text")
key(popup._search, qt.Qt.Key_Escape)
wait(150)
check(not popup.isVisible(), "Esc closes the popup")
check(len(g.scene.all_node_items()) == 2, "Esc adds nothing")

section("drag from an output port to an input port")
g.select()
thresh = g.add('ThresholdNode', x=300, y=160)
xf = g.add('TransformsNode', x=600, y=160)
med = g.add('MedianFilterNode', x=600, y=-200)
# Everything the mouse will touch has to be inside the viewport.
canvas.frame_all()
wait(200)
out_port = src.get_port('volume_out', is_input=False)
in_port = thresh.get_port('volume_in', is_input=True)
drag(out_port.scene_center(), in_port.scene_center())
edge = g.scene.get_incoming_edge(in_port)
check(edge is not None and edge.source_port is out_port,
      "dragging between ports made an edge")
check(len(g.scene._edges) == 2, "two edges now")

section("a drag onto a port of the wrong type makes no edge")
drag(out_port.scene_center(),
     xf.get_port('transform_in', is_input=True).scene_center())
check(g.scene.get_incoming_edge(
    xf.get_port('transform_in', is_input=True)) is None,
      "volume to transform is refused")
drag(out_port.scene_center(), qt.QPointF(450, 330))
check(len(g.scene._edges) == 2, "dropping on empty canvas makes no edge")
check(g.scene._drag_edge is None, "no dangling drag edge")

section("click selects, number key views")
orig_sample = src.node_data.execute
mouse(qt.QEvent.MouseButtonPress, node_center(thresh))
mouse(qt.QEvent.MouseButtonRelease, node_center(thresh))
wait(100)
check(thresh.isSelected() and not src.isSelected(), "a click selects the node")
canvas.setFocus()
key(canvas, qt.Qt.Key_1, '1')
g.wait_async()
wait(500)
check(not g.errors(), f"no errors ({g.errors()})")
check(g.out(thresh, 'volume_out') is not None, "key 1 ran the chain")
check(thresh._viewer_slot == 1, "the node shows slot badge 1")

section("double-click opens the properties")
c = node_center(thresh)
mouse(qt.QEvent.MouseButtonPress, c)
mouse(qt.QEvent.MouseButtonRelease, c)
mouse(qt.QEvent.MouseButtonDblClick, c)
mouse(qt.QEvent.MouseButtonRelease, c)
wait(300)
check(not editor._props_collapsible.collapsed
      and 'Threshold' in editor._props_collapsible.text,
      f"properties panel shows the node ({editor._props_collapsible.text})")

section("drag a node")
before = node_center(thresh)
drag(before, qt.QPointF(before.x() + 120, before.y() + 60))
after = node_center(thresh)
check(abs(after.x() - before.x() - 120) < 6
      and abs(after.y() - before.y() - 60) < 6,
      f"the node moved with the drag ({after.x() - before.x():.0f}, "
      f"{after.y() - before.y():.0f})")
check(g.scene.get_incoming_edge(in_port) is not None,
      "a plain drag keeps the edge")

section("drop a node on an edge to insert it")
edge = g.scene.get_incoming_edge(in_port)
a = edge.source_port.scene_center()
b = edge.target_port.scene_center()
mid = qt.QPointF((a.x() + b.x()) / 2.0, (a.y() + b.y()) / 2.0)
drag(node_center(med), mid, steps=12)
up = g.scene.get_incoming_edge(med.get_port('volume_in', is_input=True))
down = g.scene.get_incoming_edge(in_port)
check(up is not None and up.source_port.node_item is src,
      "the dropped node is fed by the upstream node")
check(down is not None and down.source_port.node_item is med,
      "the downstream node is fed by the dropped node")

section("shake a node to disconnect it")
c = node_center(med)
move(c)
mouse(qt.QEvent.MouseButtonPress, c)
for i in range(24):
    dx = 45 if i % 2 == 0 else -45
    move(qt.QPointF(c.x() + dx, c.y()), qt.Qt.LeftButton)
mouse(qt.QEvent.MouseButtonRelease, c)
wait(200)
check(g.scene.get_incoming_edge(med.get_port('volume_in', is_input=True))
      is None, "shaking removed the node's edges")
down = g.scene.get_incoming_edge(in_port)
check(down is not None and down.source_port.node_item is src,
      "the edge was spliced back around the shaken node")

section("wheel zoom and middle-button pan")
t0 = canvas.transform().m11()
wheel_global = viewport.mapToGlobal(qt.QPoint(200, 150))
wheel = qt.QWheelEvent(qt.QPointF(200, 150),
                       qt.QPointF(wheel_global.x(), wheel_global.y()),
                       qt.QPoint(0, 0), qt.QPoint(0, 120),
                       qt.Qt.NoButton, qt.Qt.NoModifier,
                       qt.Qt.NoScrollPhase, False)
app.sendEvent(viewport, wheel)
app.processEvents()
check(canvas.transform().m11() > t0, "wheel up zooms in")
h0 = canvas.horizontalScrollBar().value
v0 = canvas.verticalScrollBar().value
start = canvas.mapToScene(qt.QPoint(300, 200))
end = canvas.mapToScene(qt.QPoint(220, 150))
drag(start, end, button=qt.Qt.MiddleButton)
check(canvas.horizontalScrollBar().value != h0
      or canvas.verticalScrollBar().value != v0, "middle-drag pans")
check(not canvas._pan_active, "pan ends on release")

section("keys with the cursor over the canvas")
g.select(med)
canvas.setFocus()
key(canvas, qt.Qt.Key_Delete)
wait(150)
check('Median Filter' not in [i.node_data.NODE_NAME
                              for i in g.scene.all_node_items()],
      "Delete removes the selected node")
key(canvas, qt.Qt.Key_Z, 'z', qt.Qt.ControlModifier)
wait(150)
check('Median Filter' in [i.node_data.NODE_NAME
                          for i in g.scene.all_node_items()],
      "Ctrl+Z brings it back")
key(canvas, qt.Qt.Key_Escape)
check(not g.scene.selected_node_items(), "Esc deselects")
key(canvas, qt.Qt.Key_F, 'f')
wait(150)
screenshot("canvas_after_input")

g.finish()
