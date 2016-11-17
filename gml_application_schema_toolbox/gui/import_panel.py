# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from qgis.PyQt import uic

from gml_application_schema_toolbox.gui.import_gmlas_panel import ImportGmlasPanel
from gml_application_schema_toolbox.gui.import_xml_panel import ImportXmlPanel
from gml_application_schema_toolbox.gui.import_pyxb_panel import ImportPyxbPanel

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

        self.pyxb_panel = self.addImportPanel(
            self.tr("Import using initial POC code - with PyXB"),
            ImportPyxbPanel())

        self.gmlPathLineEdit.setText('/home/qgis/qgisgmlas/data/geosciml/mappedfeature.gml')

    def addImportPanel(self, text, panel):
        self.stackedWidget.addWidget(panel)
        self.importTypeCombo.addItem(text, panel)
        return panel

    def gml_path(self):
        return self.gmlPathLineEdit.text()

    @pyqtSlot()
    def on_gmlPathButton_clicked(self):
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Open GML file"),
            data_folder,
            self.tr("GML Files (*.gml *.xml)"))
        if path:
            self.gmlPathLineEdit.setText(path)

    @pyqtSlot(int)
    def on_importTypeCombo_currentIndexChanged(self, index):
        self.stackedWidget.setCurrentWidget(self.importTypeCombo.currentData())
