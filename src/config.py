import os
from PyQt6.QtGui import QColor

GATE_WIDTH = 64
GATE_HEIGHT = 32

TOGGLE_SIZE = 32
BULB_SIZE = 32

PIN_RADIUS = 4
WIRE_THICKNESS = 6
WIRE_ON_TOP = False

PIN_COLOR_OFF = QColor(22, 4, 12)
PIN_COLOR_ON = QColor(219, 54, 134)

BULB_COLOR_OFF = QColor(0, 0, 0)
BULB_COLOR_ON = QColor(255, 255, 255)

GATE_COLORS = {
    "NOT": QColor(191, 73, 73),
    "AND": QColor(73, 75, 191),
    "NAND": QColor(73, 183, 191),
    "OR": QColor(191, 73, 189),
    "NOR": QColor(189, 189, 11),
    "XOR": QColor(136, 73, 191),
    "XNOR": QColor(132, 191, 73),
}

GATE_INPUT_COUNTS = {
    "NOT": 1,
    "AND": 2,
    "NAND": 2,
    "OR": 2,
    "NOR": 2,
    "XOR": 2,
    "XNOR": 2,
}

GATE_LOGIC = {
    "NOT": lambda inputs: not inputs[0],
    "AND": lambda inputs: all(inputs),
    "NAND": lambda inputs: not all(inputs),
    "OR": lambda inputs: any(inputs),
    "NOR": lambda inputs: not any(inputs),
    "XOR": lambda inputs: inputs[0] != inputs[1],
    "XNOR": lambda inputs: not (inputs[0] != inputs[1]),
}

MAX_LOOPS = 1

ZOOM_MIN = 10
ZOOM_MAX = 500
ZOOM_STEP = 10

GRID_SIZE = 16

ROOT_DIR = os.path.abspath(os.curdir)
print(ROOT_DIR)