""""
To enter Virtual Envrionment:

Set-ExecutionPolicy Unrestricted -Scope Process; . .\venv\Scripts\Activate.ps1

To run Program:

srun

Quit Program Shortcut:

ctrl + `

"""
"""
Finished: full implementation of mini caption boxes. batch translation works
ToDo: Fix bugs:
    1. slow scroll on same image (text changes position): text in list assigned to different boxes
    2. mini caption boxes are created at positions that contain no jp text (just number and symbol)

"""

import sys
from PyQt5 import QtWidgets, QtCore, QtGui

from ScreenSelector import ScreenSelector
from CaptionOverlay import CaptionOverlay
from MiniCaptionBox import MiniCaptionBoxManager
from OCRWorker import OCRWorker
from TranslateWorker import TranslateWorker
from ControlBox import ControlBox

class ExitShortcut(QtCore.QObject):
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if (event.text() == '`' and event.modifiers() & QtCore.Qt.ControlModifier):
                print("Ctrl + ` detected. Exiting.")
                # QtWidgets.QApplication.quit()
                shutdown_all()
                return True
        return False

if __name__ == "__main__":
    def shutdown_all():
        ocr_worker.shutdown_now()
        translate_worker.shutdown_now()
        QtWidgets.QApplication.quit()

    app = QtWidgets.QApplication(sys.argv)

    # Ctrl + ~ exits app
    exit_filter = ExitShortcut()
    exit_filter.shutdown = shutdown_all
    app.installEventFilter(exit_filter)

    selector = ScreenSelector()
    selector.show()

    overlay = CaptionOverlay()
    # overlay.show() # shows in weird coords at start cause not properly moved yet?
    overlay.make_click_through()

    overlay.toggle_capture_box_visibility.connect(selector.toggle_visibility)

    ocr_worker = OCRWorker(selector)
    # overlay.force_translate.connect(ocr_worker.force_translate_now)

    translate_worker = TranslateWorker()

    mini_manager = MiniCaptionBoxManager()

    control_box = ControlBox()
    control_box.btn1.clicked.connect(selector.toggle_visibility)
    control_box.btn2.clicked.connect(mini_manager.toggle_visibility)
    control_box.btn3.clicked.connect(ocr_worker.force_capture)
    control_box.btn3.clicked.connect(translate_worker.force_translate)
    control_box.show()

    ocr_worker.result_ready.connect(translate_worker.receive_texts)
    # translate_worker.translated.connect(overlay.update_text)
    ocr_worker.mini_coords.connect(mini_manager.on_new_coords)
    translate_worker.translated.connect(mini_manager.on_new_texts)
    translate_worker.translated.connect(control_box.show_translations)

    ocr_worker.start()
    translate_worker.start()

    sys.exit(app.exec_())