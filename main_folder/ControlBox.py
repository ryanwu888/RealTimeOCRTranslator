from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QWidget, QLabel, QTextEdit, QVBoxLayout, QHBoxLayout, QPushButton, QFrame
from ScreenSelector import ScreenSelector

import ctypes
import ctypes.wintypes

class ControlBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Control Box")
        self.resize(600, 400)

        # Main vertical layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header: label + buttons
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)

        # Create buttons
        self.btn1 = QPushButton("Toggle Capture Box")
        self.btn2 = QPushButton("Toggle Display Box")
        self.btn3 = QPushButton("Force Translate")

        # Apply uniform font size to buttons
        button_style = "font-size: 10pt;"
        for btn in (self.btn1, self.btn2, self.btn3):
            btn.setStyleSheet(button_style)

        # Add buttons to layout
        header_layout.addWidget(self.btn1)
        header_layout.addWidget(self.btn2)
        header_layout.addWidget(self.btn3)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Translation history text area (borderless)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setAcceptRichText(False)
        # Remove any frame/border
        self.text.setFrameShape(QFrame.NoFrame)
        self.text.setFrameShadow(QFrame.Plain)
        self.text.setLineWidth(0)
        self.text.setMidLineWidth(0)
        # Remove extra margins/padding
        self.text.setStyleSheet(
            "QTextEdit { border: none; background: transparent; margin: 0px; padding: 0px; }"
        )
        self.text.setViewportMargins(0, 0, 0, 0)
        main_layout.addWidget(self.text)

        hwnd = int(self.winId())
        exclude_window_from_capture(hwnd)

    @pyqtSlot(list, list)
    def show_translations(self, jp_list, en_list):
        # Only add a blank line if there is already something in the box
        if self.text.toPlainText():
            self.text.append("")   

        for jp, en in zip(jp_list, en_list):
            self.text.append(jp)
            self.text.append("→ " + en)

        # Scroll to bottom
        self.text.moveCursor(self.text.textCursor().End)


def exclude_window_from_capture(hwnd):
    WDA_EXCLUDEFROMCAPTURE = 0x11  # Exclude from capture
    SetWindowDisplayAffinity = ctypes.windll.user32.SetWindowDisplayAffinity
    SetWindowDisplayAffinity.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
    SetWindowDisplayAffinity.restype = ctypes.wintypes.BOOL
    SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)