# -*- coding: utf-8 -*-

import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSlot


WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'import_xml_panel.ui'))


class ImportXmlPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(ImportXmlPanel, self).__init__(parent)
        self.setupUi(self)

    @pyqtSlot()
    def on_gmlPathButton_clicked(self):
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Open GML file"),
            data_folder,
            self.tr("GML files (*.gml *.xml)"))
        if path:
            self.gmlPathLineEdit.setText(path)
