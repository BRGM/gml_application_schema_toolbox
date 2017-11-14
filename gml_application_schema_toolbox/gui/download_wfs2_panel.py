# -*- coding: utf-8 -*-

import os
import owslib_hacks
import owslib

from owslib.wfs import WebFeatureService
from owslib.feature.wfs200 import WFSCapabilitiesReader

from tempfile import NamedTemporaryFile

import logging

from qgis.core import QgsCoordinateTransform, QgsCoordinateReferenceSystem, \
    QgsOwsConnection
from qgis.gui import QgsNewHttpConnection
from qgis.utils import iface

from qgis.PyQt.QtCore import (
    Qt, pyqtSignal, pyqtSlot,
    QSettings,
    QUrl, QFile, QIODevice, QUrlQuery)
# from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog, QTableWidgetItem, QDialog
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt import uic

from gml_application_schema_toolbox.core.logging import log
from gml_application_schema_toolbox.core.proxy import qgis_proxy_settings
from gml_application_schema_toolbox.core.settings import settings
from gml_application_schema_toolbox.core.xml_utils import xml_parse, no_prefix
from gml_application_schema_toolbox.core.qgis_urlopener import remote_open_from_qgis

from .xml_dialog import XmlDialog

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'download_wfs2_panel.ui'))

class DownloadWfs2Panel(BASE, WIDGET):

    file_downloaded = pyqtSignal(str)

    def __init__(self, parent=None):
        super(DownloadWfs2Panel, self).__init__(parent)
        self.setupUi(self)

        self.downloadProgressBar.setVisible(False)

        self.featureLimitBox.setValue(int(settings.value('default_maxfeatures')))

        self.refresh_connections()
        self.connectionCombo.currentTextChanged.connect(self.on_change_connection)

        self.file_downloaded.connect(self.on_file_downloaded)

    def refresh_connections(self):
        # populate connection combo box
        self.connectionCombo.clear()
        for name in QgsOwsConnection.connectionList("wfs"):
            self.connectionCombo.addItem(name)

        self.connectionCombo.setCurrentText(QgsOwsConnection.selectedConnection("wfs"))
        self.on_change_connection(self.connectionCombo.currentText())

    def wfs(self):
        conn = QgsOwsConnection("wfs", self.connectionCombo.currentText())
        uri = conn.uri().param('url')
        version = conn.uri().param('version')
        if version == "auto":
            # detect version
            u = QUrlQuery(uri)
            u.addQueryItem("request", "GetCapabilities")
            u.addQueryItem("acceptversions", "2.0.0,1.1.0,1.0.0")

            xml, ns_map = xml_parse(remote_open_from_qgis(u.query()))
            root = xml.getroot()
            versions = [v.text for v in root.findall("./ows:ServiceIdentification/ows:ServiceTypeVersion", ns_map)]
            # take the greatest version, if more than one
            version = sorted(versions)[-1]
            
        with qgis_proxy_settings():
            return WebFeatureService(url=uri, version=version)

    @pyqtSlot(str)
    def on_change_connection(self, currentConnection):
        has_selection = currentConnection != ''
        self.connectBtn.setEnabled(has_selection)
        self.newConnectionBtn.setEnabled(has_selection)
        self.editConnectionBtn.setEnabled(has_selection)
        self.removeConnectionBtn.setEnabled(has_selection)
        self.showCapabilitiesButton.setEnabled(has_selection)
        if has_selection:
            QgsOwsConnection.setSelectedConnection("wfs", currentConnection)

    @pyqtSlot()
    def on_connectBtn_clicked(self):
        self.setCursor(Qt.WaitCursor)
        wfs = self.wfs()

        self.featureTypesTableWidget.clear()
        self.featureTypesTableWidget.setRowCount(0)
        self.featureTypesTableWidget.setHorizontalHeaderLabels(["Feature type", "Title"])
        row = 0
        for feature_type, md in wfs.contents.items():
            self.featureTypesTableWidget.insertRow(row)

            item = QTableWidgetItem(feature_type)
            item.setData(Qt.UserRole, feature_type)
            self.featureTypesTableWidget.setItem(row, 0, item)

            item = QTableWidgetItem(md.title)
            self.featureTypesTableWidget.setItem(row, 1, item)
            row += 1

        self.featureTypesTableWidget.sortItems(1)


        self.storedQueriesListWidget.clear()
        if hasattr(wfs, "storedqueries"):
            for stored_query in list(wfs.storedqueries):
                params = ', '.join(["{}: {}".format(p.name, p.type) for p in stored_query.parameters])
                self.storedQueriesListWidget.addItem("{}({})".format(stored_query.id, params))

        self.storedQueriesListWidget.sortItems()

        self.unsetCursor()

    @pyqtSlot()
    def on_editConnectionBtn_clicked(self):
        conn = self.connectionCombo.currentText()
        dlg = QgsNewHttpConnection(self,
                                   QgsNewHttpConnection.ConnectionWfs,
                                   "qgis/connections-wfs/",
                                   conn)
        dlg.setWindowTitle("Edit a WFS connection")
        if dlg.exec_() == QDialog.Accepted:
            self.refresh_connections()
            self.connectionCombo.setCurrentText(conn)

    @pyqtSlot()
    def on_newConnectionBtn_clicked(self):
        dlg = QgsNewHttpConnection(self,
                                   QgsNewHttpConnection.ConnectionWfs,
                                   "qgis/connections-wfs/")
        if dlg.exec_() == QDialog.Accepted:
            self.refresh_connections()
            self.connectionCombo.setCurrentText(dlg.name())

    @pyqtSlot()
    def on_removeConnectionBtn_clicked(self):
        conn = self.connectionCombo.currentText()
        r = QMessageBox.information(self, "Confirm removal",
                                    "Are you sure you want to remove {} connection?".format(conn),
                                    QMessageBox.Yes | QMessageBox.No)
        if r == QMessageBox.Yes:
            QgsOwsConnection.deleteConnection("wfs", conn)
            self.refresh_connections()            

    @pyqtSlot()
    def on_showCapabilitiesButton_clicked(self):
        XmlDialog(self, self.wfs().getcapabilities().read()).exec_()
        # url = WFSCapabilitiesReader().capabilities_url(self.uri())
        # QDesktopServices.openUrl(QUrl(url))

    @pyqtSlot()
    def on_outputPathButton_clicked(self):
        path, filter = QFileDialog.getSaveFileName(self,
            self.tr("Select output file"),
            self.outputPathLineEdit.text(),
            self.tr("GML Files (*.gml *.xml)"))
        if path:
            if os.path.splitext(path)[1] == '':
                path = '{}.gml'.format(path)
            self.outputPathLineEdit.setText(path)

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

    @pyqtSlot(str)
    def on_file_downloaded(self, path):
        self.fromFileLineEdit.setText(path)

    def selected_typenames(self):
        typenames = []
        for item in self.featureTypesTableWidget.selectedItems():
            if item.column() == 0:
                typenames.append(item.data(Qt.UserRole))
        return typenames

    def _get_bbox(self, wfs):
        """
        Get the selected bbox in the default CRS of the first selected layer.
        """
        default_crs_name = wfs.contents[self.selected_typenames()[0]].crsOptions[0]
        default_crs = QgsCoordinateReferenceSystem.fromOgcWmsCrs(str(default_crs_name))
        assert default_crs.isValid()
        transform = QgsCoordinateTransform(self.bboxWidget.crs(), default_crs)
        bbox = transform.transformBoundingBox(self.bboxWidget.rectangle())
        return [bbox.xMinimum(),
                bbox.yMinimum(),
                bbox.xMaximum(),
                bbox.yMaximum(),
                default_crs_name]

    def download(self):
        wfs = self.wfs()

        typenames = self.selected_typenames()
        if len(typenames) == 0:
            return

        params = {
            'typename': typenames,
            'maxfeatures': self.featureLimitBox.value(),
        }

        if self.bboxGroupBox.isChecked():
            if self.bboxWidget.value() == '':
                QMessageBox.warning(self,
                                    self.windowTitle(),
                                    "Extent is empty")
                return
            if not self.bboxWidget.isValid():
                QMessageBox.warning(self,
                                    self.windowTitle(),
                                    "Extent is invalid")
                return
            params['bbox'] = self._get_bbox(wfs)

        try:
            with qgis_proxy_settings():
                response = wfs.getfeature(**params)
        except owslib.util.ServiceException as e:
            QMessageBox.critical(self, 'ServiceException', str(e))
            return
        xml = response.read()

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

        path = self.outputPathLineEdit.text()
        if path == '':
            with NamedTemporaryFile(suffix='.gml') as out:
                path = out.name
        with open(path, 'w', encoding='utf8') as out:
            out.write(xml)

        return path

    def download_stored_query(self):
        pass
