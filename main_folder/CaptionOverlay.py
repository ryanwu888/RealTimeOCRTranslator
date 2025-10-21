from PyQt5 import QtWidgets, QtCore, QtGui
# import win is installed and working, but not recognized, use type ignore to get rid of warning
import win32gui # type: ignore
import win32con # type: ignore


class CaptionOverlay(QtWidgets.QWidget):
    toggle_capture_box_visibility = QtCore.pyqtSignal()  # Signal for toggling capture box
    force_translate = QtCore.pyqtSignal()  # 🔁 New signal for forcing re-translation

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            QtCore.Qt.Tool |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.dragging = False
        self.mouse_offset = QtCore.QPoint()
        self.custom_position = None

        # Label for translated text
        self.label = QtWidgets.QLabel(self)
        self.label.setFont(QtGui.QFont("Arial", 12))
        self.label.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)

        # ❌ Close app button
        self.close_button = QtWidgets.QPushButton("❌", self)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet(
            "QPushButton { background-color: gray; color: white; border: none; border-radius: 12px; font-weight: bold; }"
            "QPushButton:hover { background-color: darkred; }"
        )
        self.close_button.setCursor(QtCore.Qt.PointingHandCursor)
        # self.close_button.clicked.connect(QtWidgets.QApplication.quit)
        # self.close_button.clicked.connect(shutdown_all)

        # 🫥 Toggle capture box button
        self.toggle_button = QtWidgets.QPushButton("🫥", self)
        self.toggle_button.setFixedSize(24, 24)
        self.toggle_button.setStyleSheet(
            "QPushButton { background-color: gray; color: white; border: none; border-radius: 12px; font-weight: bold; }"
            "QPushButton:hover { background-color: darkgray; }"
        )
        self.toggle_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.toggle_button.clicked.connect(self._toggle_capture_box)

        # 🔁 Force Translate button
        self.force_button = QtWidgets.QPushButton("🔁", self)
        self.force_button.setFixedSize(24, 24)
        self.force_button.setStyleSheet(
            "QPushButton { background-color: gray; color: white; border: none; border-radius: 12px; font-weight: bold; }"
            "QPushButton:hover { background-color: darkgray; }"
        )
        self.force_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.force_button.clicked.connect(self._force_translation)

    def _toggle_capture_box(self):
        self.toggle_capture_box_visibility.emit()

    def _force_translation(self):
        self.force_translate.emit()

    def update_text(self, detected, translated):
        pairs = [(jp, en) for jp, en in zip(detected, translated) if jp.strip()]
        caption = "\n\n".join([f"{jp}\n→ {en}" for jp, en in pairs])
        self.label.setText(caption)

        button_width = self.close_button.width()
        padding = 10

        self.label.setStyleSheet(
            f"""
            color: white;
            padding: 10px;
            padding-right: {button_width + padding}px;
            """
        )
        self.label.adjustSize()

        label_width = self.label.width()
        label_height = self.label.height()

        # Ensure enough height for buttons
        # min_height = self.close_button.height() + self.toggle_button.height() + 24
        min_height = (
            self.close_button.height() +
            self.toggle_button.height() +
            self.force_button.height() +
            3 * 6  # spacing between them
        )
        total_height = max(label_height, min_height)
        total_width = label_width

        self.label.move(0, 0)

        margin = 6
        self.close_button.move(total_width - button_width - margin, margin)
        self.toggle_button.move(
            total_width - button_width - margin,
            self.close_button.y() + self.close_button.height() + 4
        )
        self.force_button.move(
            total_width - button_width - margin,
            self.toggle_button.y() + self.toggle_button.height() + 4
        )

        if self.custom_position:
            self.setGeometry(self.custom_position.x(), self.custom_position.y(), total_width, total_height)
        else:
            screen = QtWidgets.QApplication.primaryScreen().geometry()
            x = (screen.width() - total_width) // 2
            y = screen.height() - total_height - 50
            self.setGeometry(x, y, total_width, total_height)

        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 128))
        pen = QtGui.QPen(QtGui.QColor("white"), 2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = True
            self.mouse_offset = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPos() - self.mouse_offset)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            self.custom_position = self.pos()

    def make_click_through(self):
        hwnd = int(self.winId())
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        ex_style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)