# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GmlasPluginDockWidget
                                 A QGIS plugin
 GMLAS Plugin
                             -------------------
        begin                : 2016-09-21
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Arnaud Morvan - www.camptocamp.com
        email                : arnaud.morvan@camptocamp.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import owslib_hacks
import owslib
from owslib.wfs import WebFeatureService
from owslib.feature.wfs200 import WFSCapabilitiesReader
from tempfile import NamedTemporaryFile

from qgis.PyQt.QtCore import (
    Qt, pyqtSignal, pyqtSlot,
    QSettings,
    QUrl, QFile, QIODevice)
# from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog, QListWidgetItem
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt import uic

from .xml_dialog import XmlDialog

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'download_panel.ui'))

data_folder = '/home/qgis/qgisgmlas/data'


import logging
from qgis.core import QgsMessageLog

class QgsMessageLogHandler(logging.Handler):

    def __init__(self, tag=None):
        super(QgsMessageLogHandler, self).__init__()
        self.tag = tag

    def emit(self, record):
        try:
            msg = self.format(record)
            QgsMessageLog.logMessage(msg, self.tag)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


owslib_logger = logging.getLogger('owslib')
owslib_logger.setLevel(logging.DEBUG)

owslib_handler = None
for handler in owslib_logger.handlers:
    if handler.__class__.__name__ == QgsMessageLogHandler.__name__:
        owslib_handler = handler
        break
if owslib_handler is None:
    owslib_handler = QgsMessageLogHandler('owslib')
    owslib_handler.setLevel(logging.DEBUG)
    owslib_logger.addHandler(owslib_handler)


class DownloadPanel(BASE, WIDGET):

    file_downloaded = pyqtSignal(str)

    def __init__(self, parent=None):
        super(DownloadPanel, self).__init__(parent)
        self.setupUi(self)

        self.downloadProgressBar.setVisible(False)

        self.uriComboBox.addItem('http://geoserv.weichand.de:8080/geoserver/wfs')
        self.uriComboBox.addItem('https://wfspoc.brgm-rec.fr/geoserver/ows')
        self.uriComboBox.addItem('https://wfspoc.brgm-rec.fr/constellation/WS/wfs/BRGM:GWML2')
        self.uriComboBox.addItem('http://geoserverref.brgm-rec.fr/geoserver/ows')
        self.uriComboBox.addItem('http://minerals4eu.brgm-rec.fr/deegree/services/m4eu')

    def wfs(self):
        uri = self.uriComboBox.currentText()
        return WebFeatureService(url=uri, version='2.0.0')

    @pyqtSlot()
    def on_getCapabilitiesButton_clicked(self):
        wfs = self.wfs()

        self.featureTypesListWidget.clear()
        for feature_type in list(wfs.contents):
            item = QListWidgetItem(feature_type)
            item.setData(Qt.UserRole, feature_type)
            self.featureTypesListWidget.addItem(item)

        self.storedQueriesListWidget.clear()
        for stored_query in list(wfs.storedqueries):
            self.storedQueriesListWidget.addItem(stored_query.id)

    @pyqtSlot()
    def on_showCapabilitiesButton_clicked(self):
        XmlDialog(self, self.wfs().getcapabilities().read()).exec_()

        # url = WFSCapabilitiesReader().capabilities_url(self.uri())
        # QDesktopServices.openUrl(QUrl(url))

    @pyqtSlot()
    def on_downloadButton_clicked(self):
        self.downloadProgressBar.setValue(0)
        self.downloadProgressBar.setVisible(True)
        self.setCursor(Qt.WaitCursor)
        try:
            if self.datasetsTabWidget.currentIndex() == 0:
                out = self.download()
            if self.datasetsTabWidget.currentIndex() == 1:
                out = self.download_stored_query()
        finally:
            self.downloadProgressBar.setVisible(False)
            self.unsetCursor()
        if out is not None:
            self.file_downloaded.emit(out)

    def selected_typenames(self):
        typenames = []
        for item in self.featureTypesListWidget.selectedItems():
            typenames.append(item.data(Qt.UserRole))
        return typenames

    def download(self):
        wfs = self.wfs()

        params = {
            'typename': ','.join(self.selected_typenames()),
            'maxfeatures': self.featureLimitBox.value(),
        }
        if self.bboxGroupBox.isChecked():
            params['bbox'] = '({})'.format(self.bboxLineEdit().text())
        '''
        srsname='urn:x-ogc:def:crs:EPSG:31468'
        '''

        try:
            response = wfs.getfeature(**params)
        except owslib.util.ServiceException as e:
            QMessageBox.critical(self, 'ServiceException', str(e))
            return
        xml = response.read()

        XmlDialog(self, xml).exec_()

        doc = QDomDocument()
        if not doc.setContent(xml):
            return
        root = doc.documentElement()
        exception = root.firstChildElement('ows:Exception')
        if not exception.isNull():
            QMessageBox.critical(self,
                                 'ows:Exception',
                                 exception.text())
            return

        with NamedTemporaryFile(suffix='.gml', delete=False) as out:
            out.write(bytes(xml, 'UTF-8'))
            path = out.name

        return path

    def download_stored_query(self):
        pass
