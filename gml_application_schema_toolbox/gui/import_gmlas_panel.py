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
import tempfile
from io import BytesIO

from osgeo import gdal, osr
from owslib.etree import etree
from qgis.core import QgsMessageLog
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, pyqtSlot
from qgis.PyQt.QtWidgets import QApplication, QListWidgetItem, QMessageBox
from qgis.utils import iface

from gml_application_schema_toolbox.__about__ import __title__
from gml_application_schema_toolbox.core.load_gmlas_in_qgis import import_in_qgis
from gml_application_schema_toolbox.core.proxy import qgis_proxy_settings
from gml_application_schema_toolbox.gui import InputError
from gml_application_schema_toolbox.gui.gmlas_panel_mixin import GmlasPanelMixin
from gml_application_schema_toolbox.toolbelt import PlgLogger, PlgOptionsManager

WIDGET, BASE = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "..", "ui", "import_gmlas_panel.ui")
)

gdal.UseExceptions()


class ImportGmlasPanel(BASE, WIDGET, GmlasPanelMixin):
    def __init__(self, parent=None, gml_path=None):
        super(ImportGmlasPanel, self).__init__(parent)
        self.log = PlgLogger().log
        self.setupUi(self)

        # map to the plugin log handler
        self.plg_logger = PlgLogger()
        self.plg_settings = PlgOptionsManager().get_plg_settings()

        self.gmlasConfigLineEdit.setText(self.plg_settings.impex_gmlas_config)
        self.acceptLanguageHeaderInput.setText(self.plg_settings.network_language)
        self.set_access_mode(self.plg_settings.access_mode_as_str)

        g = "gml_application_schema_toolbox"
        self.layers_group.setSettingGroup(g)
        self.gmlas_bbox_group.setSettingGroup(g)
        self.gmlas_options_group.setSettingGroup(g)
        self.target_db_group.setSettingGroup(g)

        self.parent = parent
        self._gml_path = gml_path

    def gml_path(self):
        if self._gml_path:
            return self._gml_path
        return self.parent.gml_path()

    def showEvent(self, event):
        # Cannot do that in the constructor. The project is not fully setup when
        # it is called
        if not self.destSrs.crs().isValid():
            self.destSrs.setCrs(iface.mapCanvas().mapSettings().destinationCrs())
        BASE.showEvent(self, event)

    # Read XML file and substitute form parameters
    def gmlas_config(self):
        path = self.gmlasConfigLineEdit.text()
        if path == "":
            raise InputError(self.tr("You must select a GMLAS config file"))

        xmlConfig = etree.parse(self.gmlasConfigLineEdit.text())

        # Set parameters
        c = xmlConfig.getroot()

        for lyr_md in c.iter("ExposeMetadataLayers"):
            lyr_md.text = str(self.ogrExposeMetadataLayersCheckbox.isChecked()).lower()
        for lyr_bldg in c.iter("LayerBuildingRules"):
            for n in lyr_bldg.iter("RemoveUnusedLayers"):
                n.text = str(self.ogrRemoveUnusedLayersCheckbox.isChecked()).lower()
            for n in lyr_bldg.iter("RemoveUnusedFields"):
                n.text = str(self.ogrRemoveUnusedFieldsCheckbox.isChecked()).lower()

        for http_hdr in c.findall("XLinkResolution/URLSpecificResolution/HTTPHeader"):
            name = http_hdr.find("Name").text
            if name == "Accept-Language":
                http_hdr.find("Value").text = self.acceptLanguageHeaderInput.text()

        textConfig = BytesIO()
        xmlConfig.write(textConfig, encoding="utf-8", xml_declaration=False)
        # Write config in temp file
        tf = tempfile.NamedTemporaryFile(
            prefix="gmlasconf_", suffix=".xml", delete=False
        )
        tf.write(textConfig.getvalue())
        tf.close()
        self.plg_logger.log(
            "Temporary configuration file created '{}' for conversion.".format(
                str(tf.name)
            )
        )

        return tf.name

    def gmlas_datasource(self) -> gdal.Dataset:
        gmlasconf = self.gmlas_config()
        datasourceFile = self.gml_path()

        self.plg_logger.log(
            f"Opening GMLAS file '{datasourceFile}', using the configuration file: '{gmlasconf}'",
            log_level=4,
        )

        if datasourceFile == "":
            raise InputError(self.tr("You must select a input file or URL"))
        isXsd = datasourceFile.endswith(".xsd")
        isUrl = datasourceFile.startswith("http")
        swapCoordinates = self.swapCoordinatesCombo.currentText()
        driverConnection = ""
        openOptions = ["EXPOSE_METADATA_LAYERS=YES", "CONFIG_FILE={}".format(gmlasconf)]

        openOptions.append("SWAP_COORDINATES={}".format(swapCoordinates))

        if isXsd:
            driverConnection = "GMLAS:"
            openOptions.append("XSD={}".format(datasourceFile))
        elif isUrl:
            driverConnection = "GMLAS:/vsicurl_streaming/{}".format(datasourceFile)
        else:
            driverConnection = "GMLAS:{}".format(datasourceFile)
        gdal.SetConfigOption("GDAL_HTTP_UNSAFESSL", "YES")
        gdal.SetConfigOption(
            "GDAL_HTTP_USERAGENT", self.plg_settings.network_http_user_agent
        )

        with qgis_proxy_settings():
            return gdal.OpenEx(driverConnection, open_options=openOptions)

    @pyqtSlot()
    def on_loadLayersButton_clicked(self):
        self.setCursor(Qt.WaitCursor)
        try:
            self.validate()
        except InputError as e:
            e.show()
        finally:
            self.unsetCursor()

    def validate(self):
        data_source = self.gmlas_datasource()

        if data_source is None:
            QMessageBox.critical(
                self,
                __title__,
                self.tr("Failed to open file using OGR GMLAS driver"),
            )
            return

        ogrMetadataLayerPrefix = "_ogr_"

        self.datasetsListWidget.clear()
        for i in range(0, data_source.GetLayerCount()):
            layer = data_source.GetLayer(i)
            layer_name = layer.GetName()
            if not layer_name.startswith(ogrMetadataLayerPrefix):
                feature_count = layer.GetFeatureCount()

                item = QListWidgetItem("{} ({})".format(layer_name, feature_count))
                item.setData(Qt.UserRole, layer_name)
                self.datasetsListWidget.addItem(item)

        self.datasetsListWidget.sortItems()
        self.datasetsListWidget.selectAll()

    def selected_layers(self):
        layers = []
        for item in self.datasetsListWidget.selectedItems():
            layers.append(item.data(Qt.UserRole))
        return layers

    def dataset_creation_options(self):
        options = []
        if (
            self.databaseWidget.get_database_connection is None
            or self.databaseWidget.get_db_format in ("sqlite", "spatialite")
        ):
            options.append("-dsco SPATIALITE=YES")
        return options

    def layer_creation_options(self):
        options = []
        if self.databaseWidget.get_database_connection:
            if self.databaseWidget.get_db_format in ("postgresql", "postgres"):
                schema = self.databaseWidget.schema_create()
                options.append("-lco SCHEMA={}".format(schema or "public"))
                if self.access_mode() == "overwrite":
                    options.append("-lco OVERWRITE=YES")
        # Reproject
        # TODO Remove default SRID when we will handle destSrs widget
        options.append("-lco SRID=4326")
        if self.reprojectCheck.isChecked():
            options.append(f"-lco SRID={self.destSrs.crs().authid()}")
            self.plg_logger.log(
                "Dest CRS : {}".format(self.destSrs.crs().authid()), log_level=4
            )
        return options

    def set_access_mode(self, value):
        if value is None:
            self.createRadioButton.setChecked(True)
        if value == "update":
            self.updateRadioButton.setChecked(True)
        if value == "append":
            self.appendRadioButton.setChecked(True)
        if value == "overwrite":
            self.overwriteRadioButton.setChecked(True)

    def access_mode(self):
        if self.createRadioButton.isChecked():
            return None
        if self.updateRadioButton.isChecked():
            return "update"
        if self.appendRadioButton.isChecked():
            return "append"
        if self.overwriteRadioButton.isChecked():
            return "overwrite"

    def dest_srs(self):
        srs = osr.SpatialReference()
        srs.ImportFromWkt(self.destSrs.crs().toWkt())
        assert srs.Validate() == 0
        return srs

    def src_srs(self):
        srs = osr.SpatialReference()
        srs.ImportFromWkt(self.sourceSrs.crs().toWkt())
        assert srs.Validate() == 0
        return srs

    def translate_options(self):
        options = []
        if not self.forceNullableCheckbox.isChecked():
            options.append("-forceNullable")
        if self.skipFailuresCheckbox.isChecked():
            options.append("-skipfailures")
        return options

    def import_params(self, dest: str, provider: str) -> dict:
        """Build the parameters dictionary for GDAL import.

        :param dest: database name or path
        :type dest: str
        :param provider: driver to use to convert with GDAL
        :type provider: str

        :raises InputError: [description]
        :raises InputError: [description]

        :return: [description]
        :rtype: dict
        """
        options = []
        options.append(f"-f {provider}")

        gmlasconf = self.gmlas_config()

        # TODO Handle in dataset open options method
        options.append(f"-oo CONFIG_FILE={gmlasconf}")

        # TODO Handle in dataset open options method
        if self.ogrExposeMetadataLayersCheckbox.isChecked():
            options.append("-oo EXPOSE_METADATA_LAYERS=YES")

        # TODO Handle source CRS with widget
        # if self.sourceSrsCheck.isChecked():
        #     params["srcSRS"] = self.src_srs()

        if self.convertToLinearCheckbox.isChecked():
            options.append("-nlt CONVERT_TO_LINEAR")

        dataset_creation_options = self.dataset_creation_options()
        [options.append(opt) for opt in dataset_creation_options]
        layer_creation_options = self.layer_creation_options()
        [options.append(opt) for opt in layer_creation_options]
        translation_options = self.translate_options()
        [options.append(opt) for opt in translation_options]

        # if self.plg_settings.debug_mode:
        #     options.append("--debug ON")

        gml_path = self.gml_path()
        self.plg_logger.log("GDAL OPTIONS: {}".format(options), log_level=4)
        params = {
            "INPUT_FILE": f"GMLAS:{gml_path}",
            "CONVERT_ALL_LAYERS": True,
            "OPTIONS": " ".join(options),
            "OUTPUT": dest,
        }
        return params

        # TODO Handle AccessMode

        # TODO Handle selected layers
        # layers = self.selected_layers()
        # if len(layers) > 0:
        #     params["layers"] = self.selected_layers()
        #     if self.ogrExposeMetadataLayersCheckbox.isChecked():
        #         params["layers"] = params["layers"] + [
        #             "_ogr_fields_metadata",
        #             "_ogr_layer_relationships",
        #             "_ogr_layers_metadata",
        #             "_ogr_other_metadata",
        #         ]

        # TODO Handle spatial extent
        # if self.gmlas_bbox_group.isChecked():
        #     if self.bboxWidget.value() == "":
        #         raise InputError("Extent is empty")
        #     if not self.bboxWidget.isValid():
        #         raise InputError("Extent is invalid")
        #     bbox = self.bboxWidget.rectangle()
        #     params["spatFilter"] = (
        #         bbox.xMinimum(),
        #         bbox.yMinimum(),
        #         bbox.xMaximum(),
        #         bbox.yMaximum(),
        #     )
        #     srs = osr.SpatialReference()
        #     srs.ImportFromWkt(self.bboxWidget.crs().toWkt())
        #     assert srs.Validate() == 0
        #     params["spatSRS"] = srs

    def do_load(self, append_to_db: str = None, append_to_schema: str = None):
        """Load selected GMLAS into a database. If no database is selected \
        (placeholder), a temporary SQLite database is created.

        :param append_to_db: [description], defaults to None
        :type append_to_db: str, optional
        :param append_to_schema: [description], defaults to None
        :type append_to_schema: str, optional
        """
        gdal.SetConfigOption("OGR_SQLITE_SYNCHRONOUS", "OFF")
        gdal.SetConfigOption("GDAL_HTTP_UNSAFESSL", "YES")
        gdal.SetConfigOption(
            "GDAL_HTTP_USERAGENT", self.plg_settings.network_http_user_agent
        )

        def error_handler(err, err_no, msg):
            if err >= gdal.CE_Warning:
                QgsMessageLog.logMessage(
                    "{} {}: {}".format(err, err_no, msg), __title__
                )

        schema = None
        if self.databaseWidget.get_database_connection is None:
            db_format = None
        else:
            db_format = self.databaseWidget.get_db_format

        # Create temp SQLite database if no connection is selected
        if db_format == "postgres":
            dest_db_name = f"{self.databaseWidget.get_database_connection.uri()}"
            schema = self.databaseWidget.selected_schema
            provider = "PostgreSQL"
            self.plg_logger.log(f"PostgreSQL schema: {schema}", log_level=4)
        elif db_format == "sqlite" or db_format == "spatialite":
            dest_db_name = self.databaseWidget.get_db_name_or_path
            provider = "SQLite"
        else:
            with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp:
                dest_db_name = tmp.name
                provider = "SQLite"
                self.plg_logger.log(f"Temp SQLite: {dest_db_name}", log_level=4)

        params = self.import_params(dest_db_name, provider)

        # TODO Handle append_to_db, accessMode, append_to_schema

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            gdal.PushErrorHandler(error_handler)
            self.translate_processing(params)
            self.plg_logger.log("Dataset translated", log_level=3)
            if append_to_db is None:
                import_in_qgis(
                    gmlas_uri=dest_db_name,
                    provider=provider,
                    auto_join=self.autoJoinCheckbox.isChecked(),
                    add_form_code=self.addCodeToForm.isChecked(),
                    schema=schema,
                )

        except InputError as e:
            e.show()
        except RuntimeError as e:
            QMessageBox.warning(None, __title__, e.args[0])
        finally:
            QApplication.restoreOverrideCursor()
            gdal.PopErrorHandler()
