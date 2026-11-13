import os
from PyQt6.QtGui import QColor

GATE_WIDTH = 64
GATE_HEIGHT = 32

TOGGLE_SIZE = 32

PIN_RADIUS = 4
WIRE_THICKNESS = 6
WIRE_ON_TOP = False

PIN_COLOR_OFF = QColor(22, 4, 12)
PIN_COLOR_ON = QColor(219, 54, 134)

GATE_COLORS = {
    "AND": QColor(73, 75, 191),
    "NOT": QColor(191, 73, 73),
}

GATE_INPUT_COUNTS = {
    "AND": 2,
    "NOT": 1,
}

GATE_LOGIC = {
    "AND": lambda inputs: all(inputs),
    "NOT": lambda inputs: not inputs[0],
}

MAX_LOOPS = 64

ZOOM_MIN = 10
ZOOM_MAX = 500
ZOOM_STEP = 10

GRID_SIZE = 16

ROOT_DIR = os.path.abspath(os.curdir)