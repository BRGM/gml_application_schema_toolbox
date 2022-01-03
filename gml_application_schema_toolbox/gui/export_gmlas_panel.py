#! python3  # noqa: E265

"""
/***************************************************************************
 ExportGmlasPanel
                                 A QGIS plugin
 GMLAS Plugin
                             -------------------
        begin                : 2016-12-08
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
from pathlib import Path
from tempfile import NamedTemporaryFile

from osgeo import gdal, osr
from qgis.core import (
    QgsDataSourceUri,
    QgsProcessingFeatureSourceDefinition,
    QgsVectorLayer,
)
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QDialog, QFileDialog
from qgis.utils import iface

from gml_application_schema_toolbox.gui import InputError
from gml_application_schema_toolbox.gui.gmlas_panel_mixin import GmlasPanelMixin
from gml_application_schema_toolbox.toolbelt import PlgLogger, PlgOptionsManager

WIDGET, BASE = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "..", "ui", "export_gmlas_panel.ui")
)


gdal.UseExceptions()


class ExportGmlasPanel(BASE, WIDGET, GmlasPanelMixin):
    def __init__(self, parent=None):
        super(ExportGmlasPanel, self).__init__(parent)
        self.log = PlgLogger().log
        self.setupUi(self)
        self.plg_settings = PlgOptionsManager().get_plg_settings()

        self.gmlasConfigLineEdit.setText(self.plg_settings.impex_gmlas_config)

    def showEvent(self, event):
        # Cannot do that in the constructor. The project is not fully setup when
        # it is called
        if not self.srsSelectionWidget.crs().isValid():
            self.srsSelectionWidget.setCrs(
                iface.mapCanvas().mapSettings().destinationCrs()
            )
        BASE.showEvent(self, event)

    @pyqtSlot()
    def on_gmlPathButton_clicked(self):
        filepath, suffix_filter = QFileDialog.getSaveFileName(
            parent=self,
            caption=self.tr("Save GML file"),
            directory="",
            filter=self.tr("GML files (*.gml *.xml)"),
        )
        if filepath:
            filepath = Path(filepath)
            filepath = filepath.with_suffix(".gml")
            self.gmlPathLineEdit.setText(str(filepath))

    @pyqtSlot()
    def on_xsdPathButton_clicked(self):
        cur_dir = os.path.dirname(self.gmlasConfigLineEdit.text())

        filepath, suffix_filter = QFileDialog.getOpenFileName(
            parent=self,
            caption=self.tr("Open XML schema definition file"),
            directory=cur_dir,
            filter=self.tr("XSD Files (*.xsd)"),
        )

        if filepath:
            self.xsdPathLineEdit.setText(filepath)

    def dst_datasource_name(self):
        gml_path = self.gmlPathLineEdit.text()
        if gml_path == "":
            raise InputError("You must select a GML output file")
        return gml_path

    def dataset_creation_options(self):
        config_file = self.gmlasConfigLineEdit.text()
        if config_file == "":
            raise InputError("You must select a GMLAS config file")

        options = {"CONFIG_FILE": config_file}

        xsd_path = self.xsdPathLineEdit.text()
        if xsd_path != "":
            options["INPUT_XSD"] = xsd_path

        return options

    def set_params(self):
        provider = self.databaseWidget.get_db_format
        uri = self.databaseWidget.get_database_connection
        src_layer = QgsVectorLayer(uri.uri(), "source", provider)

        options = []
        options.append('-f "GMLAS"')
        if provider == "postgres":
            options.append(f"-oo SCHEMAS={self.databaseWidget.selected_schema}")
        options.append("-oo LIST_ALL_TABLES=YES")
        # Reproject
        options.append(f"-t_srs {self.srsSelectionWidget.crs().authid()}")
        dataset_creation_options = self.dataset_creation_options()
        options.append(f"-dsco CONFIG_FILE={dataset_creation_options['CONFIG_FILE']}")
        if "INPUT_XSD" in dataset_creation_options:
            options.append(f"-dsco INPUT_XSD={dataset_creation_options['INPUT_XSD']}")
        # if self.plg_settings.debug_mode:
        #     options.append("--debug ON")

        gml_path = self.dst_datasource_name()
        params = {
            "INPUT": src_layer,
            "CONVERT_ALL_LAYERS": True,
            "OPTIONS": " ".join(options),
            "OUTPUT": gml_path,
        }
        return params

    # @pyqtSlot()
    # def on_exportButton_clicked(self):
    def accept(self):
        try:
            self.translate_processing(self.set_params())
        except InputError as e:
            e.show()

        QDialog.accept(self)
