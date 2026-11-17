import math

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import (
    QBrush,
    QPen,
    QFont,
    QPixmap,
    QPainter,
)
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
)

import config


font_name = None
snapping_enabled = False


def snap_position(x, y):
    return (
        x // config.GRID_SIZE * config.GRID_SIZE + config.GRID_SIZE / 2,
        y // config.GRID_SIZE * config.GRID_SIZE + config.GRID_SIZE / 2,
    )


def make_wire_pen(powered=False):
    color = config.PIN_COLOR_ON if powered else config.PIN_COLOR_OFF
    pen = QPen(color, config.WIRE_THICKNESS)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def update_power(scene):
    gates = [item for item in scene.items() if isinstance(item, (Gate, Bulb))]
    for _ in range(config.MAX_LOOPS):
        if not any([gate.evaluate() for gate in gates]):
            break


def render_item_pixmap(item_type, gate_name=None):
    temp_scene = QGraphicsScene()
    if item_type == "gate":
        temp_scene.addItem(Gate(gate_name, 0, 0))
    elif item_type == "toggle":
        temp_scene.addItem(Toggle(0, 0))
    else:
        temp_scene.addItem(Bulb(0, 0))

    rect = temp_scene.itemsBoundingRect()
    pixmap = QPixmap(math.ceil(rect.width()), math.ceil(rect.height()))
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    temp_scene.render(painter, QRectF(0, 0, rect.width(), rect.height()), rect)
    painter.end()
    return pixmap


def delete_scene_item(item, scene):
    pins = item.pins if isinstance(item, Gate) else [item.pin]
    for pin in pins:
        for wire in list(pin.wires):
            wire.remove()
    scene.removeItem(item)
    update_power(scene)


class Wire(QGraphicsLineItem):
    def __init__(self, output_pin, input_pin):
        super().__init__()
        self.output_pin = output_pin
        self.input_pin = input_pin

        self.setZValue(2)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        output_pin.wires.append(self)
        input_pin.wires.append(self)
        self.update_position()
        self.update_color()

    def update_position(self):
        a = self.output_pin.scenePos()
        b = self.input_pin.scenePos()
        self.setLine(a.x(), a.y(), b.x(), b.y())

    def update_color(self):
        self.setPen(make_wire_pen(self.output_pin.powered))

    def remove(self):
        self.output_pin.wires.remove(self)
        self.input_pin.wires.remove(self)
        if self.scene() is not None:
            update_power(self.scene())
            self.scene().removeItem(self)


def connect_pins(output_pin, input_pin, scene):
    for wire in list(input_pin.wires):
        wire.remove()
    scene.addItem(Wire(output_pin, input_pin))
    update_power(scene)


class Pin(QGraphicsEllipseItem):
    def __init__(self, gate, is_input, x, y):
        super().__init__(
            -config.PIN_RADIUS,
            -config.PIN_RADIUS,
            config.PIN_RADIUS * 2,
            config.PIN_RADIUS * 2,
            gate,
        )
        self.setZValue(1)
        self.gate = gate
        self.is_input = is_input
        self.powered = False
        self.wires = []

        self.drag_line = None
        self.drag_anchor = None

        self.brush = QBrush(config.PIN_COLOR_OFF)
        self.pen = QPen(config.PIN_COLOR_OFF.darker(200), 4)
        self.pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)

        self.setPos(x, y)
        self.setBrush(self.brush)
        self.setPen(self.pen)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    def set_powered(self, powered):
        self.powered = powered

        if powered:
            self.brush.setColor(config.PIN_COLOR_ON)
            self.pen.setColor(config.PIN_COLOR_ON.darker(200))
        else:
            self.brush.setColor(config.PIN_COLOR_OFF)
            self.pen.setColor(config.PIN_COLOR_OFF.darker(200))
        self.setBrush(self.brush)
        self.setPen(self.pen)

        for wire in self.wires:
            wire.update_color()

    def update_wires(self):
        for wire in self.wires:
            wire.update_position()

    def can_connect_to(self, other):
        if other.gate is self.gate:
            return False
        return self.is_input != other.is_input

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return

        if self.is_input and self.wires:
            wire = self.wires[0]
            self.drag_anchor = wire.output_pin
            wire.remove()
        else:
            self.drag_anchor = self

        self.drag_line = QGraphicsLineItem()
        self.drag_line.setZValue(1)
        self.drag_line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene().addItem(self.drag_line)
        self.update_drag_line(event.scenePos())
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_line is not None:
            self.update_drag_line(event.scenePos())

    def mouseReleaseEvent(self, event):
        if self.drag_line is None:
            return

        anchor = self.drag_anchor
        target = self.valid_target_at(event.scenePos())
        scene = self.scene()

        scene.removeItem(self.drag_line)
        self.drag_line = None
        self.drag_anchor = None

        if target is not None:
            if target.is_input:
                connect_pins(anchor, target, scene)
            else:
                connect_pins(target, anchor, scene)

    def valid_target_at(self, scene_pos):
        for item in self.scene().items(scene_pos):
            if isinstance(item, Pin) and self.drag_anchor.can_connect_to(item):
                return item
        return None

    def update_drag_line(self, scene_pos):
        anchor = self.drag_anchor
        target = self.valid_target_at(scene_pos)

        end = target.scenePos() if target is not None else scene_pos
        start = anchor.scenePos()
        self.drag_line.setLine(start.x(), start.y(), end.x(), end.y())

        output_pin = target if anchor.is_input else anchor
        powered = output_pin is not None and output_pin.powered
        self.drag_line.setPen(make_wire_pen(powered))


class Toggle(QGraphicsRectItem):
    def __init__(self, x, y):
        super().__init__(0, 0, config.TOGGLE_SIZE, config.TOGGLE_SIZE)
        self.setZValue(0)
        self.brush = QBrush(config.PIN_COLOR_OFF)
        self.pen = QPen(config.PIN_COLOR_OFF.darker(200), 4)
        self.pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)

        self.setPos(x, y)
        self.setBrush(self.brush)
        self.setPen(self.pen)

        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        )
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setAcceptHoverEvents(True)

        self.powered = False
        pin_y = config.TOGGLE_SIZE / 2
        self.pin = Pin(self, False, config.TOGGLE_SIZE, pin_y)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            global snapping_enabled
            if snapping_enabled:
                self.setPos(*snap_position(value.x(), value.y()))
            self.pin.update_wires()
        return super().itemChange(change, value)

    def toggle(self):
        self.powered = not self.powered
        self.pin.set_powered(self.powered)

        if self.powered:
            self.brush.setColor(config.PIN_COLOR_ON)
            self.pen.setColor(config.PIN_COLOR_ON.darker(200))
        else:
            self.brush.setColor(config.PIN_COLOR_OFF)
            self.pen.setColor(config.PIN_COLOR_OFF.darker(200))
        self.setBrush(self.brush)
        self.setPen(self.pen)
        update_power(self.scene())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.toggle()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Backspace:
            delete_scene_item(self, self.scene())
        else:
            super().keyPressEvent(event)

    def hoverEnterEvent(self, event):
        self.setFocus()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.clearFocus()
        super().hoverLeaveEvent(event)


class Bulb(QGraphicsRectItem):
    def __init__(self, x, y):
        super().__init__(0, 0, config.TOGGLE_SIZE, config.TOGGLE_SIZE)
        self.setZValue(0)
        self.brush = QBrush(config.BULB_COLOR_OFF)
        self.pen = QPen(config.BULB_COLOR_OFF.darker(200), 4)
        self.pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)

        self.setPos(x, y)
        self.setBrush(self.brush)
        self.setPen(self.pen)

        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        )
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setAcceptHoverEvents(True)

        self.powered = False
        pin_y = config.TOGGLE_SIZE / 2
        self.pin = Pin(self, True, 0, pin_y)

    def evaluate(self):
        powered = bool(self.pin.wires) and self.pin.wires[0].output_pin.powered
        if self.pin.powered != powered:
            self.pin.set_powered(powered)

            if powered:
                self.brush.setColor(config.BULB_COLOR_ON)
                self.pen.setColor(config.BULB_COLOR_ON.darker(200))
            else:
                self.brush.setColor(config.BULB_COLOR_OFF)
                self.pen.setColor(config.BULB_COLOR_OFF.darker(200))
            self.setBrush(self.brush)
            self.setPen(self.pen)

        return False

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            global snapping_enabled
            if snapping_enabled:
                self.setPos(*snap_position(value.x(), value.y()))
            self.pin.update_wires()
        return super().itemChange(change, value)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Backspace:
            delete_scene_item(self, self.scene())
        else:
            super().keyPressEvent(event)

    def hoverEnterEvent(self, event):
        self.setFocus()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.clearFocus()
        super().hoverLeaveEvent(event)


class Gate(QGraphicsRectItem):
    def __init__(self, name, x, y):
        super().__init__(0, 0, config.GATE_WIDTH, config.GATE_HEIGHT)
        self.name = name
        self.pins = []
        self.setZValue(0)
        self.setPos(x, y)
        self.setBrush(QBrush(config.GATE_COLORS[name]))
        pen = QPen(config.GATE_COLORS[name].darker(200), 4)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self.setPen(pen)

        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setAcceptHoverEvents(True)

        font = QFont(font_name, 16)
        font.setWeight(700)

        label = QGraphicsSimpleTextItem(name, self)
        label.setFont(font)
        label.setBrush(QBrush(config.GATE_COLORS[name].darker(200)))

        text_rect = label.boundingRect()
        label.setPos(
            (config.GATE_WIDTH - text_rect.width()) / 2,
            (config.GATE_HEIGHT - text_rect.height()) / 2,
        )

        input_count = config.GATE_INPUT_COUNTS[name]
        for i in range(input_count):
            gap = (config.GATE_HEIGHT - input_count * config.PIN_RADIUS) / (
                input_count + 1
            )
            pin_y = gap * (i + 1) + config.PIN_RADIUS * i + config.PIN_RADIUS / 2
            # pin_y = config.GATE_HEIGHT * (i + 1) / (input_count + 1)
            self.pins.append(Pin(self, True, 0, pin_y))

        output_count = 1
        for i in range(output_count):
            gap = (config.GATE_HEIGHT - output_count * config.PIN_RADIUS) / (
                output_count + 1
            )
            pin_y = gap * (i + 1) + config.PIN_RADIUS * i + config.PIN_RADIUS / 2
            # pin_y = config.GATE_HEIGHT * (i + 1) / (output_count + 1)
            self.pins.append(Pin(self, False, config.GATE_WIDTH, pin_y))

        self.input_pins = [pin for pin in self.pins if pin.is_input]
        self.output_pin = next(pin for pin in self.pins if not pin.is_input)

    def evaluate(self):
        changed = False

        for pin in self.input_pins:
            powered = bool(pin.wires) and pin.wires[0].output_pin.powered
            if pin.powered != powered:
                pin.set_powered(powered)
                changed = True

        powered = config.GATE_LOGIC[self.name]([pin.powered for pin in self.input_pins])
        if self.output_pin.powered != powered:
            self.output_pin.set_powered(powered)
            changed = True

        return changed

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Backspace:
            delete_scene_item(self, self.scene())
        else:
            super().keyPressEvent(event)

    def hoverEnterEvent(self, event):
        self.setFocus()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.clearFocus()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            global snapping_enabled
            if snapping_enabled:
                self.setPos(*snap_position(value.x(), value.y()))
            for pin in self.pins:
                pin.update_wires()
        return super().itemChange(change, value)
