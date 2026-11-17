import os

from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import (
    QBrush,
    QTransform,
    QFontDatabase,
    QFont,
    QPixmap,
    QPainter,
)
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
)

import config
import items


class BarItem(QLabel):
    def __init__(self, view, item_type, gate_name=None, parent=None):
        super().__init__(parent)
        self.view = view
        self.item_type = item_type
        self.gate_name = gate_name
        self.drag_offset = None
        self.drag_preview = None

        self.pixmap_img = items.render_item_pixmap(item_type, gate_name)
        self.setPixmap(self.pixmap_img)
        self.setFixedSize(self.pixmap_img.size())
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.drag_offset is None or not (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            return

        if self.drag_preview is None:
            self.drag_preview = QLabel(self.window())
            self.drag_preview.setPixmap(self.pixmap_img)
            self.drag_preview.setFixedSize(self.pixmap_img.size())
            self.drag_preview.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            self.drag_preview.show()
            self.drag_preview.raise_()

        pos = self.window().mapFromGlobal(event.globalPosition().toPoint())
        self.drag_preview.move(pos - self.drag_offset)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.drag_offset is None:
            return

        if self.drag_preview is not None:
            self.drag_preview.deleteLater()
            self.drag_preview = None

            view_pos = self.view.viewport().mapFromGlobal(
                event.globalPosition().toPoint()
            )
            if self.view.viewport().rect().contains(view_pos):
                offset = QPointF(
                    self.pixmap_img.width() / 2 - self.drag_offset.x(),
                    self.pixmap_img.height() / 2 - self.drag_offset.y(),
                )
                scene_pos = self.view.mapToScene(view_pos) + offset / (
                    self.view.zoom / 100
                )

                if self.item_type == "gate":
                    self.view.add_gate(self.gate_name, scene_pos)
                elif self.item_type == "toggle":
                    self.view.add_toggle(scene_pos)
                elif self.item_type == "bulb":
                    self.view.add_bulb(scene_pos)

        self.drag_offset = None


class ItemBar(QFrame):
    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.setObjectName("ItemBar")
        self.setFixedHeight(60)
        self.setStyleSheet(
            """
            #ItemBar {
                background-color: #282828;
                border-top: 4px solid #424242;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(20)

        for gate_name in config.GATE_LOGIC:
            layout.addWidget(
                BarItem(view, "gate", gate_name),
                alignment=Qt.AlignmentFlag.AlignVCenter,
            )
        layout.addWidget(
            BarItem(view, "toggle"), alignment=Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(BarItem(view, "bulb"), alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch()

        trash_pixmap = QPixmap(os.path.join(config.ROOT_DIR, "content/imgs/trash.png"))
        if not trash_pixmap.isNull() and trash_pixmap.height() > 48:
            trash_pixmap = trash_pixmap.scaledToHeight(
                36, Qt.TransformationMode.SmoothTransformation
            )
        self.trash_label = QLabel()
        self.trash_label.setPixmap(trash_pixmap)
        self.trash_label.setFixedSize(trash_pixmap.size())
        layout.addWidget(self.trash_label, alignment=Qt.AlignmentFlag.AlignVCenter)


class GateView(QGraphicsView):
    zoom_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__(QGraphicsScene())
        self.trash = None
        self.zoom = 100
        self.wheel_remainder = 0

        self.setSceneRect(-5000, -5000, 10000, 10000)
        self.centerOn(0, 0)

        brush = QBrush(
            QPixmap(os.path.join(config.ROOT_DIR, "content/imgs/circle tile.png"))
        )
        brush.setTransform(QTransform.fromScale(0.25, 0.25))
        self.setBackgroundBrush(brush)
        self.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.Antialiasing,
            True,
        )

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            items.snapping_enabled = True
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            items.snapping_enabled = False
        else:
            super().keyReleaseEvent(event)

    def mouseReleaseEvent(self, event):
        grabber = self.scene().mouseGrabberItem()
        super().mouseReleaseEvent(event)

        if (
            event.button() == Qt.MouseButton.LeftButton
            and isinstance(grabber, (items.Gate, items.Toggle, items.Bulb))
            and self.trash_widget is not None
        ):
            trash_pos = self.trash_widget.mapFromGlobal(
                event.globalPosition().toPoint()
            )
            if self.trash_widget.rect().contains(trash_pos):
                items.delete_scene_item(grabber, self.scene())

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

    def add_gate(self, name, scene_pos=None):
        if scene_pos is None:
            scene_pos = self._cursor_scene_pos()
        gate = items.Gate(
            name,
            scene_pos.x() - config.GATE_WIDTH / 2,
            scene_pos.y() - config.GATE_HEIGHT / 2,
        )
        self.scene().addItem(gate)
        items.update_power(self.scene())

    def add_toggle(self, scene_pos=None):
        if scene_pos is None:
            scene_pos = self._cursor_scene_pos()
        toggle = items.Toggle(
            scene_pos.x() - config.TOGGLE_SIZE / 2,
            scene_pos.y() - config.TOGGLE_SIZE / 2,
        )
        self.scene().addItem(toggle)

    def add_bulb(self, scene_pos=None):
        if scene_pos is None:
            scene_pos = self._cursor_scene_pos()
        bulb = items.Bulb(
            scene_pos.x() - config.BULB_SIZE / 2,
            scene_pos.y() - config.BULB_SIZE / 2,
        )
        self.scene().addItem(bulb)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Logic Gates")
        self.resize(1000, 600)

        font_id = QFontDatabase.addApplicationFont(
            os.path.join(config.ROOT_DIR, "content/fonts/JetBrainsMono.ttf")
        )
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        items.font_name = font_families[0]

        self.view = GateView()
        self.item_bar = ItemBar(self.view)
        self.view.trash_widget = self.item_bar.trash_label
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFont(QFont(items.font_name, 16))
        self.zoom_label.setContentsMargins(8, 8, 8, 8)
        self.zoom_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setRowStretch(0, 1)
        layout.addWidget(self.view, 0, 0)
        layout.addWidget(
            self.zoom_label,
            0,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        )
        layout.addWidget(self.item_bar, 1, 0)
        self.zoom_label.raise_()

        self.view.zoom_changed.connect(lambda zoom: self.zoom_label.setText(f"{zoom}%"))
        self.view.setFocus()
