# -*- coding: utf-8 -*-

import os
import owslib_hacks
import owslib

from owslib.wfs import WebFeatureService
from owslib.feature.wfs200 import WFSCapabilitiesReader

from tempfile import NamedTemporaryFile

import logging

from qgis.core import QgsCoordinateTransform, QgsCoordinateReferenceSystem, \
    QgsOwsConnection, QgsProject, QgsMessageLog, QgsSettings
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

from .import_gmlas_panel import ImportGmlasPanel
from .import_xml_panel import ImportXmlPanel
from .xml_dialog import XmlDialog

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'load_panel.ui'))

class LoadWfs2Panel(BASE, WIDGET):

    file_downloaded = pyqtSignal(str)

    def __init__(self, parent=None):
        super(LoadWfs2Panel, self).__init__(parent)
        self.setupUi(self)

        self.featureLimitBox.setValue(int(settings.value('default_maxfeatures')))

        self.refresh_connections()
        self.connectionCombo.currentTextChanged.connect(self.on_change_connection)

        self.file_downloaded.connect(self.on_file_downloaded)

        self.xml_panel = ImportXmlPanel(self)
        self.gmlas_panel = ImportGmlasPanel(self)
        self.stackedWidget.addWidget(self.xml_panel)
        self.stackedWidget.addWidget(self.gmlas_panel)

        self.xmlModeRadio.toggled.connect(self.on_xml)
        self.relationalModeRadio.toggled.connect(self.on_gmlas)

        v = settings.value("default_import_method")
        self.xmlModeRadio.setChecked(v == 'xml')
        self.relationalModeRadio.setChecked(v == 'gmlas')

        self.featureTypesTableWidget.itemSelectionChanged.connect(self.on_wfs_layer_selection_changed)

        g = "gml_application_schema_toolbox"
        self.wfs_options_group.setSettingGroup(g)
        self.gmlas_panel.layers_group.setSettingGroup(g)
        self.gmlas_panel.gmlas_bbox_group.setSettingGroup(g)
        self.gmlas_panel.gmlas_options_group.setSettingGroup(g)
        self.gmlas_panel.target_db_group.setSettingGroup(g)
        self.xml_panel.xml_options_group.setSettingGroup(g)

    def refresh_connections(self):
        # populate connection combo box
        self.connectionCombo.clear()
        for name in QgsOwsConnection.connectionList("wfs"):
            self.connectionCombo.addItem(name)

        self.connectionCombo.setCurrentText(QgsOwsConnection.selectedConnection("wfs"))
        self.on_change_connection(self.connectionCombo.currentText())

    def wfs(self):
        name = self.connectionCombo.currentText()
        conn = QgsOwsConnection("wfs", name)
        uri = conn.uri().param('url')
        req_version = conn.uri().param('version')
        s = QgsSettings()
        checked_version = s.value("qgis/connections-wfs/{}/checked_version".format(name), False)
        if req_version == "auto" or not checked_version:
            # detect version
            u = QUrlQuery()
            u.addQueryItem("request", "GetCapabilities")
            if req_version == "auto":
                u.addQueryItem("acceptversions", "2.0.0,1.1.0,1.0.0")
            elif not checked_version:
                u.addQueryItem("version", req_version)
            final_url = QUrl(uri)
            final_url.setQuery(u)

            xml, ns_map = xml_parse(remote_open_from_qgis(final_url.toString()))
            root = xml.getroot()
            if 'ows' in ns_map:
                versions = [v.text for v in root.findall("./ows:ServiceIdentification/ows:ServiceTypeVersion", ns_map)]
            else:
                versions = [v.text for v in root.findall("./ServiceIdentification/ServiceTypeVersion", ns_map)]
            if not versions:
                if 'version' in root.attrib:
                    versions = [root.attrib['version']]
            if not versions:
                raise RuntimeError("Cannot determine WFS version")
            # take the greatest version, if more than one
            version = sorted(versions)[-1]

            if version != req_version:
                QgsMessageLog.logMessage("Requested WFS version {}, got {}".format(req_version, version))
            else:
                s.setValue("qgis/connections-wfs/{}/checked_version".format(name), True)
        else:
            version = req_version
            
        with qgis_proxy_settings():
            return WebFeatureService(url=uri, version=version)

    def on_xml(self, enabled):
        if enabled:
            self.stackedWidget.setCurrentWidget(self.xml_panel)
    def on_gmlas(self, enabled):
        if enabled:
            self.stackedWidget.setCurrentWidget(self.gmlas_panel)

    def on_wfs_layer_selection_changed(self):
        self.loadButton.setEnabled(self.featureTypesTableWidget.selectedItems() != [])

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
        self.setCursor(Qt.WaitCursor)
        try:
            if self.datasetsTabWidget.currentIndex() == 0:
                out = self.download()
            if self.datasetsTabWidget.currentIndex() == 1:
                out = self.download_stored_query()
        finally:
            self.unsetCursor()
        if out is not None:
            self.file_downloaded.emit(out)

    @pyqtSlot(str)
    def on_file_downloaded(self, path):
        self.gmlPathLineEdit.setText(path)
        self.gmlPathLineEdit.setText(path)

    @pyqtSlot()
    def on_gmlPathButton_clicked(self):
        gml_path = settings.value("gml_path", "")
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Open GML file"),
            gml_path,
            self.tr("GML files or XSD (*.gml *.xml *.xsd)"))
        if path:
            settings.setValue("gml_path", os.path.dirname(path))
            self.gmlPathLineEdit.setText(path)

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
        transform = QgsCoordinateTransform(self.bboxWidget.crs(), default_crs, QgsProject.instance())
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

        if self.bbox_group.isChecked():
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

    @pyqtSlot()
    def on_loadFromFileButton_clicked(self):
        if self.xmlModeRadio.isChecked():
            self.xml_panel.do_load()
        else:
            self.gmlas_panel.do_load()

    @pyqtSlot()
    def on_loadButton_clicked(self):
        self.on_downloadButton_clicked()
        self.on_loadFromFileButton_clicked()
