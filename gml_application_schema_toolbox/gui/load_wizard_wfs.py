#! python3  # noqa: E265

# ############################################################################
# ########## Imports ###############
# ##################################

# Standard library
import os

from lxml.etree import XMLSyntaxError
from owslib.util import ServiceException
from owslib.wfs import WebFeatureService
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsOwsConnection,
    QgsProject,
    QgsSettings,
)
from qgis.gui import QgsNewHttpConnection
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QUrl, QUrlQuery, pyqtSlot
from qgis.PyQt.QtWidgets import QDialog, QMessageBox, QTableWidgetItem, QWizardPage
from qgis.PyQt.QtXml import QDomDocument

# project
from gml_application_schema_toolbox.core.proxy import qgis_proxy_settings
from gml_application_schema_toolbox.core.qgis_urlopener import remote_open_from_qgis
from gml_application_schema_toolbox.core.xml_utils import xml_parse
from gml_application_schema_toolbox.gui.wait_cursor_context import WaitCursor
from gml_application_schema_toolbox.gui.xml_dialog import XmlDialog
from gml_application_schema_toolbox.toolbelt import PlgLogger, PlgOptionsManager

# ############################################################################
# ########## Globals ###############
# ##################################

PAGE_1A_W, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "..", "ui", "load_wizard_wfs.ui")
)


# ############################################################################
# ########## Classes ###############
# ##################################


class LoadWizardWFS(QWizardPage, PAGE_1A_W):
    def __init__(self, parent, next_id):
        super().__init__(parent)
        self.log = PlgLogger().log
        self.setupUi(self)
        plg_settings = PlgOptionsManager().get_plg_settings()

        self.featureLimitBox.setValue(plg_settings.network_max_features)

        self.refresh_connections()
        self.connectionCombo.currentTextChanged.connect(self.on_change_connection)

        self._is_complete = False
        self.featureTypesTableWidget.itemSelectionChanged.connect(
            self.on_wfs_layer_selection_changed
        )

        g = "gml_application_schema_toolbox"
        self.wfs_options_group.setSettingGroup(g)

        # gml_path cache
        self._gml_path = None

        self._next_id = next_id
        if __debug__:
            self.log(message=f"DEBUG {__name__} loaded.", log_level=5)

    def on_wfs_layer_selection_changed(self):
        self._is_complete = self.featureTypesTableWidget.selectedItems() != []
        self.completeChanged.emit()

    def isComplete(self):
        return self._is_complete

    def nextId(self):
        return self._next_id

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
        uri = conn.uri().param("url")
        req_version = conn.uri().param("version")
        s = QgsSettings()
        checked_version = s.value(
            "qgis/connections-wfs/{}/checked_version".format(name), False
        )
        if req_version == "auto" or not checked_version:
            # detect version
            u = QUrlQuery()
            u.addQueryItem("request", "GetCapabilities")
            u.addQueryItem("service", "WFS")
            if req_version == "auto":
                u.addQueryItem("acceptversions", "2.0.0,1.1.0,1.0.0")
            elif not checked_version:
                u.addQueryItem("version", req_version)
            final_url = QUrl(uri)
            final_url.setQuery(u)

            xml, ns_map = xml_parse(remote_open_from_qgis(final_url.toString()))
            root = xml.getroot()
            if "ows" in ns_map:
                versions = [
                    v.text
                    for v in root.findall(
                        "./ows:ServiceIdentification/ows:ServiceTypeVersion", ns_map
                    )
                ]
            else:
                versions = [
                    v.text
                    for v in root.findall(
                        "./ServiceIdentification/ServiceTypeVersion", ns_map
                    )
                ]
            if not versions:
                if "version" in root.attrib:
                    versions = [root.attrib["version"]]
            if not versions:
                raise RuntimeError("Cannot determine WFS version")
            # take the greatest version, if more than one
            version = sorted(versions)[-1]

            if version != req_version:
                QgsMessageLog.logMessage(
                    "Requested WFS version {}, got {}".format(req_version, version)
                )
            else:
                s.setValue("qgis/connections-wfs/{}/checked_version".format(name), True)
        else:
            version = req_version

        with qgis_proxy_settings():
            return WebFeatureService(url=uri, version=version)

    @pyqtSlot(str)
    def on_change_connection(self, currentConnection):
        has_selection = currentConnection != ""
        self.connectBtn.setEnabled(has_selection)
        self.newConnectionBtn.setEnabled(has_selection)
        self.editConnectionBtn.setEnabled(has_selection)
        self.removeConnectionBtn.setEnabled(has_selection)
        self.showCapabilitiesButton.setEnabled(has_selection)
        if has_selection:
            QgsOwsConnection.setSelectedConnection("wfs", currentConnection)

    @pyqtSlot()
    def on_connectBtn_clicked(self):
        with WaitCursor():
            return self.on_connectBtn_clicked_()

    def on_connectBtn_clicked_(self):
        wfs = self.wfs()

        self.featureTypesTableWidget.clear()
        self.featureTypesTableWidget.setRowCount(0)
        self.featureTypesTableWidget.setHorizontalHeaderLabels(
            ["Feature type", "Title"]
        )
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
        try:
            if hasattr(wfs, "storedqueries"):
                for stored_query in list(wfs.storedqueries):
                    params = ", ".join(
                        [
                            "{}: {}".format(p.name, p.type)
                            for p in stored_query.parameters
                        ]
                    )
                    self.storedQueriesListWidget.addItem(
                        "{}({})".format(stored_query.id, params)
                    )
                self.datasetsTabWidget.setTabEnabled(
                    self.datasetsTabWidget.indexOf(self.tab_2), True
                )
            else:
                self.datasetsTabWidget.setTabEnabled(
                    self.datasetsTabWidget.indexOf(self.tab_2), False
                )
        except ServiceException:
            self.datasetsTabWidget.setTabEnabled(
                self.datasetsTabWidget.indexOf(self.tab_2), False
            )
        except XMLSyntaxError:
            self.datasetsTabWidget.setTabEnabled(
                self.datasetsTabWidget.indexOf(self.tab_2), False
            )

        self.storedQueriesListWidget.sortItems()

    @pyqtSlot()
    def on_editConnectionBtn_clicked(self):
        conn = self.connectionCombo.currentText()
        dlg = QgsNewHttpConnection(
            self, QgsNewHttpConnection.ConnectionWfs, "qgis/connections-wfs/", conn
        )
        dlg.setWindowTitle("Edit a WFS connection")
        if dlg.exec_() == QDialog.Accepted:
            self.refresh_connections()
            self.connectionCombo.setCurrentText(conn)

    @pyqtSlot()
    def on_newConnectionBtn_clicked(self):
        dlg = QgsNewHttpConnection(
            self, QgsNewHttpConnection.ConnectionWfs, "qgis/connections-wfs/"
        )
        if dlg.exec_() == QDialog.Accepted:
            self.refresh_connections()
            self.connectionCombo.setCurrentText(dlg.name())

    @pyqtSlot()
    def on_removeConnectionBtn_clicked(self):
        conn = self.connectionCombo.currentText()
        r = QMessageBox.information(
            self,
            "Confirm removal",
            "Are you sure you want to remove {} connection?".format(conn),
            QMessageBox.Yes | QMessageBox.No,
        )
        if r == QMessageBox.Yes:
            QgsOwsConnection.deleteConnection("wfs", conn)
            self.refresh_connections()

    @pyqtSlot()
    def on_showCapabilitiesButton_clicked(self):
        XmlDialog(self, self.wfs().getcapabilities().read()).exec_()

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
        transform = QgsCoordinateTransform(
            self.bboxWidget.crs(), default_crs, QgsProject.instance()
        )
        bbox = transform.transformBoundingBox(self.bboxWidget.rectangle())
        return [
            bbox.xMinimum(),
            bbox.yMinimum(),
            bbox.xMaximum(),
            bbox.yMaximum(),
            str(default_crs_name),
        ]

    def download(self, output_path):
        with WaitCursor():
            if self.datasetsTabWidget.currentIndex() == 0:
                self.download_features(output_path)
            if self.datasetsTabWidget.currentIndex() == 1:
                self.download_stored_query(output_path)

    def download_features(self, output_path):
        wfs = self.wfs()

        typenames = self.selected_typenames()
        if len(typenames) == 0:
            return

        params = {
            "typename": typenames,
        }
        if self.limitChkBox.isChecked():
            params["maxfeatures"] = self.featureLimitBox.value()

        if self.bbox_group.isChecked():
            if self.bboxWidget.value() == "":
                QMessageBox.warning(self, self.windowTitle(), "Extent is empty")
                return
            if not self.bboxWidget.isValid():
                QMessageBox.warning(self, self.windowTitle(), "Extent is invalid")
                return
            params["bbox"] = self._get_bbox(wfs)

        try:
            with qgis_proxy_settings():
                response = wfs.getfeature(**params)
        except ServiceException as e:
            QMessageBox.critical(self, "ServiceException", str(e))
            return
        xml = response.read()

        doc = QDomDocument()
        if not doc.setContent(xml):
            return
        root = doc.documentElement()
        exception = root.firstChildElement("ows:Exception")
        if not exception.isNull():
            QMessageBox.critical(self, "ows:Exception", exception.text())
            return

        # depending on WFS versions, we get either a str or bytes
        if isinstance(xml, str):
            xml = xml.encode("utf8")
        with open(output_path, "wb") as out:
            out.write(xml)

    def download_stored_query(self, output_path):
        pass
