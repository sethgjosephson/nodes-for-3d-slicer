"""
Visual and data-type constants shared across the node graph engine.
All colours are (R, G, B) tuples matching Slicer's dark theme.
"""

# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------
CANVAS_BG          = (26,  26,  26)
GRID_DOT_COLOR     = (55,  55,  55)
GRID_SPACING       = 20          # pixels between dots

# ---------------------------------------------------------------------------
# Node geometry
# ---------------------------------------------------------------------------
NODE_WIDTH         = 190
NODE_TITLE_HEIGHT  = 26
NODE_BODY_HEIGHT   = 34          # below title bar; grows if many ports
NODE_CORNER_RADIUS = 5
NODE_BORDER_NORMAL = (68,  68,  68)
NODE_BORDER_SELECT = (55, 121, 181)   # Slicer blue
NODE_TITLE_FG      = (230, 230, 230)
NODE_BODY_BG       = (52,  52,  52)
NODE_DIRTY_COLOR   = (220, 140,  30)  # orange dot when re-execution needed
SLOT_BADGE_COLORS  = {
    1:  ( 55, 121, 181),   # blue
    2:  ( 90, 170,  90),   # green
    3:  (220, 140,  30),   # orange
    4:  (200,  85, 145),   # pink
    5:  (140, 105, 200),   # purple
    6:  ( 90, 195, 195),   # teal
    7:  (210, 195,  70),   # yellow
    8:  (200,  85,  85),   # red
    9:  (110, 175,  80),   # lime
    10: (160, 160, 160),   # grey  (bound to '0' key)
}

# ---------------------------------------------------------------------------
# Node category title-bar colours
# ---------------------------------------------------------------------------
CAT_COLOR = {
    "I/O":           (42,  90, 140),
    "Filters":       (48,  98,  48),
    "Segmentation":  (98,  48,  98),
    "Registration":  (115, 85,  28),
    "Visualization": (28,  98, 108),
    "Layout":        (72,  72,  72),
    "Utilities":     (68,  68,  68),
}
DEFAULT_CAT_COLOR  = (68,  68,  68)

# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------
PORT_RADIUS        = 7
PORT_LABEL_FONT_SZ = 8
PORT_HIT_RADIUS    = 12          # larger click target

PORT_COLORS = {
    "volume":       (210,  90,  90),   # red
    "labelmap":     ( 90, 170, 210),   # cyan
    "segmentation": (170,  90, 210),   # magenta
    "transform":    (210, 185,  70),   # gold
    "model":        ( 90, 200,  90),   # green
    "markup":       (240, 160,  60),   # orange
    "table":        (120, 195, 175),   # mint
    "plot":         (200, 110, 175),   # pink
    "text":         (185, 185, 185),   # light grey
    "color":        (140, 110, 200),   # purple
    "sequence":     ( 90, 130, 235),   # bright blue (reserved for 4D)
    "any":          (160, 160, 160),   # mid grey
}

# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------
EDGE_WIDTH         = 2.0
EDGE_CTRL_MIN      = 80          # minimum bezier control-point offset (px)
EDGE_SELECTED_CLR  = (220, 220,  60)
EDGE_DRAG_CLR      = (180, 180, 180)

# ---------------------------------------------------------------------------
# Search popup
# ---------------------------------------------------------------------------
POPUP_WIDTH        = 260
POPUP_MAX_HEIGHT   = 340
POPUP_BG           = (38,  38,  38)
POPUP_BORDER       = (80,  80,  80)
POPUP_HIGHLIGHT    = (55, 121, 181)
