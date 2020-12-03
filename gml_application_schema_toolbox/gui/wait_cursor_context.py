from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication


class WaitCursor(object):
    def __enter__(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)

    def __exit__(self, type, value, traceback):
        QApplication.restoreOverrideCursor()
