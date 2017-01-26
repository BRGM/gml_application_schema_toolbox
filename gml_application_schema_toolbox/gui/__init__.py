# -*- coding: utf-8 -*-

from qgis.PyQt.QtWidgets import QMessageBox
from gml_application_schema_toolbox import name as plugin_name


class InputError(Exception):

    def __init__(self, message=None, parent=None):
        self.message = message
        self.parent = parent

    def show(self):
        if self.message == None:
            return
        QMessageBox.warning(self.parent,
                            plugin_name(),
                            self.message)
