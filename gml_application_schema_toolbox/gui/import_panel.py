# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from qgis.PyQt import uic

from gml_application_schema_toolbox.gui.import_gmlas_panel import ImportGmlasPanel
from gml_application_schema_toolbox.gui.import_xml_panel import ImportXmlPanel

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'import_panel.ui'))


data_folder = '/home/qgis/qgisgmlas/data'


class ImportPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(ImportPanel, self).__init__(parent)
        self.setupUi(self)

        self.gmlas_panel = self.addImportPanel(
            self.tr("Import using GMLAS driver"),
            ImportGmlasPanel())

        self.xml_panel = self.addImportPanel(
            self.tr("Import as XML"),
            ImportXmlPanel())

    def addImportPanel(self, text, panel):
        self.stackedWidget.addWidget(panel)
        self.importTypeCombo.addItem(text, panel)
        return panel

    @pyqtSlot(int)
    def on_importTypeCombo_currentIndexChanged(self, index):
        self.stackedWidget.setCurrentWidget(self.importTypeCombo.currentData())
