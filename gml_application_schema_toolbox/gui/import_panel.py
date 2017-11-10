# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from qgis.PyQt import uic

from gml_application_schema_toolbox.core.settings import settings
from gml_application_schema_toolbox.gui.import_gmlas_panel import ImportGmlasPanel
from gml_application_schema_toolbox.gui.import_xml_panel import ImportXmlPanel

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'import_panel.ui'))


class ImportPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(ImportPanel, self).__init__(parent)
        self.setupUi(self)

        self.xml_panel = ImportXmlPanel()
        self.gmlas_panel = ImportGmlasPanel()
        self.stackedWidget.addWidget(self.xml_panel)
        self.stackedWidget.addWidget(self.gmlas_panel)

        self.xmlModeRadio.toggled.connect(self.on_xml)
        self.relationalModeRadio.toggled.connect(self.on_gmlas)

        v = settings.value("default_import_method")
        self.xmlModeRadio.setChecked(v == 'xml')
        self.relationalModeRadio.setChecked(v == 'gmlas')

    def on_xml(self, enabled):
        if enabled:
            self.stackedWidget.setCurrentWidget(self.xml_panel)
    def on_gmlas(self, enabled):
        if enabled:
            self.stackedWidget.setCurrentWidget(self.gmlas_panel)
