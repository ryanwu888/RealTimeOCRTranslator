from PyQt5 import QtWidgets, QtCore, QtGui
import ctypes
import ctypes.wintypes
# import win is installed and working, but not recognized, use type ignore to get rid of warning
import win32gui # type: ignore
import win32con # type: ignore


class MiniCaptionBox(QtWidgets.QWidget):
    def __init__(self, x, y, width, height):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.Tool |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setGeometry(x, y, width, height)

        # Use a layout so label always fills the box:
        # self.label = QtWidgets.QLabel(self)
        self.label = WrapLabel(self)
        self.label.setFont(QtGui.QFont("Arial", 15))
        self.label.setWordWrap(True)
        self.label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.label.setStyleSheet("color: white;")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.addWidget(self.label)
        self.label.setMargin(0)
        self.label.setContentsMargins(0, 0, 0, 0)

        hwnd = int(self.winId())
        exclude_window_from_capture(hwnd)

        self.show()

    def set_text(self, caption):
        self.label.setText(caption)
        self.auto_shrink_font(caption)

        self.show()
        self.raise_()
        self.activateWindow()
        # print("[TEXT SET]:", caption)
        print("[Mini Label] ", self.label.text())

    def auto_shrink_font(self, text, min_pt=1.0, step=0.1):
        font = QtGui.QFont(self.label.font())
        size = font.pointSizeF() or font.pointSize()
        W, H = self.label.width(), self.label.height()

        # 1) Shrink if any single word is too wide
        metrics = QtGui.QFontMetricsF(font)
        words = [w for line in text.split("\n") for w in line.split()]
        if words:
            longest = max(words, key=lambda w: metrics.horizontalAdvance(w))
            while size > min_pt and metrics.horizontalAdvance(longest) > W:
                size -= step
                font.setPointSizeF(size)
                metrics = QtGui.QFontMetricsF(font)

        # 2) Shrink if the block is still too tall
        doc = QtGui.QTextDocument()
        opt = doc.defaultTextOption()
        opt.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        # WrapAtWordBoundaryOrAnywhere will prefer spaces but allow
        # breaking after hyphens if needed—not plain mid-word.
        doc.setDefaultTextOption(opt)

        while size > min_pt:
            font.setPointSizeF(size)
            doc.setDefaultFont(font)
            doc.setPlainText(text)
            doc.setTextWidth(W)
            if doc.size().height() <= H:
                break
            size -= step

        self.label.setFont(font)
        print("Current Size Font: ", font.pointSizeF())

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 128))
        pen = QtGui.QPen(QtGui.QColor("white"), 2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 5, 5)
    
    def make_click_through(self):
        hwnd = int(self.winId())
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        ex_style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)


class MiniCaptionBoxManager:
    def __init__(self, parent=None):
        self.parent = parent
        # holds dicts: {'jp_text': str, 'box': MiniCaptionBox}
        self.items = []
        # staging until we have both coords & texts
        self.pending_coords = None
        self.pending_jp_texts = None
        self.pending_en_texts = None

        self.visible_state = True

    def on_new_coords(self, coords_list):
        """Slot to receive the fresh list of (x,y,w,h)."""
        self.pending_coords = coords_list
        self._maybe_update()

    def on_new_texts(self, jp_texts, en_texts):
        """Slot to receive both JP and EN text lists."""
        self.pending_jp_texts = jp_texts
        self.pending_en_texts = en_texts
        self._maybe_update()

    def _maybe_update(self):
        if (self.pending_coords is None or 
            self.pending_jp_texts is None or 
            self.pending_en_texts is None):
            return
        coords = self.pending_coords
        jp_texts = self.pending_jp_texts
        en_texts = self.pending_en_texts
        # clear staging
        self.pending_coords = None
        self.pending_jp_texts = None
        self.pending_en_texts = None
        # diff & reconcile
        self._diff_and_reconcile(jp_texts, en_texts, coords)

    def _diff_and_reconcile(self, jp_texts, en_texts, coords):
        new_items = []
        used_old = set()
        # 1) match existing boxes by JP text, update geometry and text
        for jp, en, (x, y, w, h) in zip(jp_texts, en_texts, coords):
            match_idx = next(
                (i for i, item in enumerate(self.items)
                 if i not in used_old and item['jp_text'] == jp),
                None
            )
            if match_idx is not None:
                item = self.items[match_idx]
                box = item['box']
                box.setGeometry(x, y, w, h)
                box.set_text(en)
                used_old.add(match_idx)
            else:
                # create a new box for unseen JP text
                box = MiniCaptionBox(x, y, w, h)
                box.make_click_through()
                if self.parent:
                    box.setParent(self.parent)
                box.set_text(en)
            new_items.append({'jp_text': jp, 'box': box})
        # 2) remove boxes that disappeared
        for i, item in enumerate(self.items):
            if i not in used_old:
                old_box = item['box']
                old_box.close()
                old_box.deleteLater()
        # 3) update roster
        self.items = new_items

    def toggle_visibility(self):
        """
        Toggle the visibility of *all* mini caption boxes.
        """
        # Flip the flag
        self.visible_state = not self.visible_state

        for item in self.items:
            box = item['box']
            if self.visible_state:
                box.show()
                # Let mouse events through again
                box.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
            else:
                box.hide()
                # Prevent clicks when hidden
                box.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)


class WrapLabel(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # still allow normal QLabel features…
        self.setWordWrap(True)
        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

    def paintEvent(self, ev):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
        # combine normal word-wrap with “wrap anywhere”
        flags  = ( QtCore.Qt.TextWordWrap
                 | QtCore.Qt.AlignLeft
                 | QtCore.Qt.AlignTop )
        painter.setPen(self.palette().color(QtGui.QPalette.WindowText))
        painter.drawText(self.rect(), flags, self.text())


def exclude_window_from_capture(hwnd):
    WDA_EXCLUDEFROMCAPTURE = 0x11  # Exclude from capture
    SetWindowDisplayAffinity = ctypes.windll.user32.SetWindowDisplayAffinity
    SetWindowDisplayAffinity.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
    SetWindowDisplayAffinity.restype = ctypes.wintypes.BOOL
    SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)