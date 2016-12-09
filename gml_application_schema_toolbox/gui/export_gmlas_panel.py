# -*- coding: utf-8 -*-
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
from osgeo import gdal, osr

from qgis.utils import iface
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QFileDialog

from gml_application_schema_toolbox.core import DEFAULT_GMLAS_CONF
from gml_application_schema_toolbox.gui import InputError
from gml_application_schema_toolbox.gui.gmlas_panel_mixin import GmlasPanelMixin


WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'export_gmlas_panel.ui'))


gdal.UseExceptions()


class ExportGmlasPanel(BASE, WIDGET, GmlasPanelMixin):

    def __init__(self, parent=None):
        super(ExportGmlasPanel, self).__init__(parent)
        self.setupUi(self)

        self.databaseWidget.set_accept_mode(QFileDialog.AcceptOpen)
        self.gmlasConfigLineEdit.setText(DEFAULT_GMLAS_CONF)

    @pyqtSlot()
    def on_gmlPathButton_clicked(self):
        path, filter = QFileDialog.getSaveFileName(self,
            self.tr("Save GML file"),
            '',
            self.tr("GML files (*.gml *.xml)"))
        if path:
            if os.path.splitext(path)[1] == '':
                path = '{}.gml'.format(path)
            self.gmlPathLineEdit.setText(path)

    @pyqtSlot()
    def on_xsdPathButton_clicked(self):
        cur_dir = os.path.dirname(self.gmlasConfigLineEdit.text())
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Open XML schema definition file"),
            cur_dir,
            self.tr("XSD Files (*.xsd)"))
        if path:
            self.xsdPathLineEdit.setText(path)

    def gmlas_config(self):
        return self.gmlasConfigLineEdit.text()

    def src_datasource(self):
        options = ['LIST_ALL_TABLES=YES']

        schema = self.databaseWidget.schema()
        if schema:
            options.append('SCHEMAS={}'.format(schema))
            #options.append('ACTIVE_SCHEMA={}'.format(schema))

        data_source = gdal.OpenEx(self.databaseWidget.datasource_name(),
                                  open_options=options)

        return data_source

    def dst_datasource_name(self):
        gml_path = self.gmlPathLineEdit.text()
        if gml_path == "":
            raise InputError("You must select a GML output file")
        return "GMLAS:{}".format(gml_path)

    def dataset_creation_options(self):
        config_file = self.gmlasConfigLineEdit.text()
        if config_file == '':
            raise InputError("You must select a GMLAS config file")

        options = {
            'CONFIG_FILE': config_file
        }

        xsd_path = self.xsdPathLineEdit.text()
        if xsd_path != '':
            options['INPUT_XSD'] = xsd_path

        return options

    def export_params(self):
        params = {
            'destNameOrDestDS': self.dst_datasource_name(),
            'srcDS': self.src_datasource(),
            'format': 'GMLAS',
            'datasetCreationOptions': self.dataset_creation_options(),
            'callback': self.import_callback
        }

        if self.bboxGroupBox.isChecked():
            if self.bboxWidget.value() == '':
                raise InputError("Extent is empty")
            if not self.bboxWidget.isValid():
                raise InputError("Extent is invalid")
            bbox = self.bboxWidget.rectangle()
            params['spatFilter'] = (bbox.xMinimum(),
                                    bbox.yMinimum(),
                                    bbox.xMaximum(),
                                    bbox.yMaximum())
            srs = osr.SpatialReference()
            srs.ImportFromWkt(self.bboxWidget.crs().toWkt())
            assert srs.Validate() == 0
            params['spatSRS'] = srs

        return params

    @pyqtSlot()
    def on_exportButton_clicked(self):
        try:
            self.translate(self.export_params())
        except InputError as e:
            e.show()
