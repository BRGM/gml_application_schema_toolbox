# -*- coding: utf-8 -*-

import os

import urllib

import traceback

from tempfile import NamedTemporaryFile

from gml_application_schema_toolbox.core.logging import log

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtCore import pyqtSlot

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'download_url_panel.ui'))


class DownloadUrlPanel(BASE, WIDGET):

    file_downloaded = pyqtSignal(str)

    def __init__(self, parent=None):
        super(DownloadUrlPanel, self).__init__(parent)
        self.setupUi(self)

    @pyqtSlot()
    def on_downloadByUrlButton_clicked(self):
        url = self.urlInput.text()
        file = self.outputInput.text()
        if file == '':
            tf = NamedTemporaryFile(mode="w+t", suffix='.gml', delete=False)
            file = tf.name

        log("Downloading url '{}' to file '{}'...".format(url, file))
        fileName = None
        try:
            fileName, headers = urllib.request.urlretrieve (url, file)
            log("File '{}' saved.".format(file))
        except Exception as e:
            log(traceback.format_exc())

        if fileName is not None:
            self.file_downloaded.emit(fileName)
