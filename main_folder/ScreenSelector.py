from PyQt5 import QtWidgets, QtCore, QtGui

class ScreenSelector(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setGeometry(QtWidgets.QApplication.primaryScreen().geometry())

        screen = QtWidgets.QApplication.primaryScreen().geometry()
        w, h = 640, 360
        x = (screen.width() - w) // 2
        y = (screen.height() - h) // 2
        self.rect_box = QtCore.QRect(x, y, w, h)

        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        self.mouse_offset = QtCore.QPoint()

        self.margin = 15  # pixels from edge to allow grabbing
        self.border_thickness = 5  # visible border

        self.visible_state = True

    def get_bbox(self):
        rect = self.rect_box.normalized()
        return (rect.left(), rect.top(), rect.right(), rect.bottom())

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtCore.Qt.transparent)
        pen = QtGui.QPen(QtCore.Qt.red, self.border_thickness)
        painter.setPen(pen)
        painter.drawRect(self.rect_box)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            pos = event.pos()
            direction = self._get_resize_direction(pos)
            if direction:
                if direction.startswith("corner"):
                    self.resizing = True
                    self.resize_direction = direction
                elif direction == "move":
                    self.dragging = True
                    self.mouse_offset = pos - self.rect_box.topLeft()

    def mouseMoveEvent(self, event):
        pos = event.pos()

        if self.resizing:
            self._resize_box(pos)
        elif self.dragging:
            self.rect_box.moveTopLeft(pos - self.mouse_offset)
        else:
            self._update_cursor(pos)

        self.update()

    def mouseReleaseEvent(self, event):
        self.resizing = False
        self.dragging = False
        self.resize_direction = None

    def _get_resize_direction(self, pos):
        r = self.rect_box
        x, y = pos.x(), pos.y()
        m = self.margin

        in_left   = abs(x - r.left())   <= m
        in_right  = abs(x - r.right())  <= m
        in_top    = abs(y - r.top())    <= m
        in_bottom = abs(y - r.bottom()) <= m

        # Corner zones
        if in_top and in_left:
            return "corner_top_left"
        if in_top and in_right:
            return "corner_top_right"
        if in_bottom and in_left:
            return "corner_bottom_left"
        if in_bottom and in_right:
            return "corner_bottom_right"

        # Edge drag zones
        if in_top or in_bottom or in_left or in_right:
            return "move"

        return None

    def _update_cursor(self, pos):
        direction = self._get_resize_direction(pos)
        if direction in ("corner_top_left", "corner_bottom_right"):
            self.setCursor(QtCore.Qt.SizeFDiagCursor)
        elif direction in ("corner_top_right", "corner_bottom_left"):
            self.setCursor(QtCore.Qt.SizeBDiagCursor)
        elif direction == "move":
            self.setCursor(QtCore.Qt.OpenHandCursor)
        else:
            self.setCursor(QtCore.Qt.ArrowCursor)

    def _resize_box(self, pos):
        if not self.resize_direction:
            return

        if self.resize_direction == "corner_top_left":
            self.rect_box.setTopLeft(pos)
        elif self.resize_direction == "corner_top_right":
            self.rect_box.setTopRight(pos)
        elif self.resize_direction == "corner_bottom_left":
            self.rect_box.setBottomLeft(pos)
        elif self.resize_direction == "corner_bottom_right":
            self.rect_box.setBottomRight(pos)

    def toggle_visibility(self):
        if self.visible_state:
            self.hide()
            self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        else:
            self.show()
            self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.visible_state = not self.visible_state