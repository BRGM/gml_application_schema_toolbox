from qgis.PyQt.QtWidgets import QMessageBox

from gml_application_schema_toolbox.__about__ import __title__


class InputError(Exception):
    def __init__(self, message=None, parent=None):
        self.message = message
        self.parent = parent

    def show(self):
        if self.message is None:
            return
        QMessageBox.warning(self.parent, __title__, self.message)
