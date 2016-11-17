# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtCore import pyqtSignal, pyqtSlot
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from qgis.PyQt import uic

from gml_application_schema_toolbox.gui.download_wfs2_panel import DownloadWfs2Panel
from gml_application_schema_toolbox.gui.download_url_panel import DownloadUrlPanel

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'download_panel.ui'))


data_folder = '/home/qgis/qgisgmlas/data'


class DownloadPanel(BASE, WIDGET):

    file_downloaded = pyqtSignal(str)

    def __init__(self, parent=None):
        super(DownloadPanel, self).__init__(parent)
        self.setupUi(self)

        self.wfs2_panel = DownloadWfs2Panel()
        self.stackedWidget.addWidget(self.wfs2_panel)
        self.wfs2_panel.file_downloaded.connect(self.file_downloaded)

        self.url_panel = DownloadUrlPanel()
        self.stackedWidget.addWidget(self.url_panel)
        self.url_panel.file_downloaded.connect(self.file_downloaded)

        self.wfs2RadioButton.setChecked(True)

    @pyqtSlot(bool)
    def on_wfs2RadioButton_toggled(self, checked):
        self.stackedWidget.setCurrentWidget(self.wfs2_panel)

    @pyqtSlot(bool)
    def on_urlRadioButton_toggled(self, checked):
        self.stackedWidget.setCurrentWidget(self.url_panel)
