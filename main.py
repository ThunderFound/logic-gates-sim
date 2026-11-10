import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QCursor, QPen, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGridLayout,
    QLabel,
    QWidget,
)

import config


def make_wire_pen(powered=False):
    color = config.PIN_COLOR_ON if powered else config.PIN_COLOR_OFF
    return QPen(color, config.WIRE_THICKNESS)


class Wire(QGraphicsLineItem):
    def __init__(self, output_pin, input_pin):
        super().__init__()
        self.output_pin = output_pin
        self.input_pin = input_pin

        self.setZValue(-1)
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
            self.scene().removeItem(self)


def connect_pins(output_pin, input_pin, scene):
    for wire in list(input_pin.wires):
        wire.remove()
    scene.addItem(Wire(output_pin, input_pin))


class Pin(QGraphicsEllipseItem):
    def __init__(self, gate, is_input, x, y):
        super().__init__(
            -config.PIN_RADIUS,
            -config.PIN_RADIUS,
            config.PIN_RADIUS * 2,
            config.PIN_RADIUS * 2,
            gate,
        )
        self.gate = gate
        self.is_input = is_input
        self.powered = False
        self.wires = []

        self.drag_line = None
        self.drag_anchor = None

        self.setPos(x, y)
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(config.PIN_COLOR_OFF))
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    def set_powered(self, powered):
        self.powered = powered
        self.setBrush(QBrush(config.PIN_COLOR_ON if powered else config.PIN_COLOR_OFF))
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
        self.drag_line.setZValue(-1)
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


class Gate(QGraphicsRectItem):
    def __init__(self, name, x, y):
        super().__init__(0, 0, config.GATE_WIDTH, config.GATE_HEIGHT)
        self.pins = []
        self.setPos(x, y)
        self.setBrush(QBrush(config.GATE_COLORS[name]))

        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        label = QGraphicsSimpleTextItem(name, self)
        text_rect = label.boundingRect()
        label.setPos(
            (config.GATE_WIDTH - text_rect.width()) / 2,
            (config.GATE_HEIGHT - text_rect.height()) / 2,
        )

        input_count = config.GATE_INPUT_COUNTS[name]
        for i in range(input_count):
            pin_y = config.GATE_HEIGHT * (i + 1) / (input_count + 1)
            self.pins.append(Pin(self, True, 0, pin_y))

        output_count = 1
        for i in range(output_count):
            pin_y = config.GATE_HEIGHT * (i + 1) / (output_count + 1)
            self.pins.append(Pin(self, False, config.GATE_WIDTH, pin_y))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for pin in self.pins:
                pin.update_wires()
        return super().itemChange(change, value)


class GateView(QGraphicsView):
    zoom_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__(QGraphicsScene())
        self.zoom = 100
        self.wheel_remainder = 0

        self.setSceneRect(-5000, -5000, 10000, 10000)
        self.centerOn(0, 0)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_1:
            self.add_gate("AND")
        elif event.key() == Qt.Key.Key_2:
            self.add_gate("NOT")
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        self.wheel_remainder += event.angleDelta().y()
        steps = int(self.wheel_remainder / 120)
        if steps != 0:
            self.wheel_remainder -= steps * 120
            self.set_zoom(
                self.zoom + steps * config.ZOOM_STEP, event.position().toPoint()
            )
        event.accept()

    def set_zoom(self, level, anchor):
        level = max(config.ZOOM_MIN, min(config.ZOOM_MAX, level))
        if level == self.zoom:
            return

        scene_point_before = self.mapToScene(anchor)

        factor = level / 100
        self.setTransform(QTransform.fromScale(factor, factor))
        self.zoom = level

        scene_point_after = self.mapToScene(anchor)
        delta = scene_point_after - scene_point_before
        view_center = self.mapToScene(self.viewport().rect().center())
        self.centerOn(view_center - delta)

        self.zoom_changed.emit(level)

    def add_gate(self, name):
        cursor = self.viewport().mapFromGlobal(QCursor.pos())
        if not self.viewport().rect().contains(cursor):
            cursor = self.viewport().rect().center()

        scene_pos = self.mapToScene(cursor)
        gate = Gate(
            name,
            scene_pos.x() - config.GATE_WIDTH / 2,
            scene_pos.y() - config.GATE_HEIGHT / 2,
        )
        self.scene().addItem(gate)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Logic Gates")
        self.resize(1000, 600)

        self.view = GateView()
        self.zoom_label = QLabel("100%")
        self.zoom_label.setContentsMargins(8, 8, 8, 8)
        self.zoom_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view, 0, 0)
        layout.addWidget(
            self.zoom_label,
            0,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        )
        self.zoom_label.raise_()

        self.view.zoom_changed.connect(lambda zoom: self.zoom_label.setText(f"{zoom}%"))
        self.view.setFocus()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
