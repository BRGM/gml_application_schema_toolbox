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
from osgeo import gdal, osr

from qgis.core import QgsMessageLog
from qgis.utils import iface

from qgis.PyQt.QtCore import QSettings, Qt, QUrl, pyqtSlot, QFile, QIODevice, QAbstractItemModel, QModelIndex
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt import uic

from processing.tools.postgis import GeoDB

from .xml_dialog import XmlDialog

DEFAULT_GMLAS_CONF = os.path.realpath(os.path.join(os.path.dirname(__file__),
                                      '..', 'conf', 'gmlasconf.xml'))

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'import_gmlas_panel.ui'))


data_folder = '/home/qgis/qgisgmlas/data'

gdal.UseExceptions()


'''
class OgrLayersMetadataModel(QStandardItemModel):

    def __init__(self, datasource=None, parent=None):
        super(OgrLayersMetadataModel, self).__init__(parent)
        self.setDatasource(datasource)

    def setDatasource(self, datasource):
        self.clear()
        if datasource is None:
            return

        metadata_layer = datasource.GetLayerByName('_ogr_layers_metadata')

        self.setColumnCount(1)
        self.setRowCount(metadata_layer.GetFeatureCount())

        row = 0
        for feature in metadata_layer:
            item = self.createItem(feature)
            self.setItem(row, item)
            row += 1

    def createItem(self, feature):
        layer_name = feature.GetField("layer_name")
        item = QStandardItem(layer_name)
        item.setData(Qt.UserRole, layer_name)
'''


class PgsqlConnectionsModel(QAbstractItemModel):

    def __init__(self, parent=None):
        super(PgsqlConnectionsModel, self).__init__(parent)

        self._settings = QSettings()
        self._settings.beginGroup('/PostgreSQL/connections/')

    def _groups(self):
        return self._settings.childGroups()

    def parent(self, index):
        return QModelIndex()

    def index(self, row, column, parent):
        return self.createIndex(row, column)

    def rowCount(self, parent):
        return len(self._groups())

    def columnCount(self, parent):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        return self._groups()[index.row()]


class ImportGmlasPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(ImportGmlasPanel, self).__init__(parent)
        self.setupUi(self)

        self.gmlasConfigLineEdit.setText(DEFAULT_GMLAS_CONF)

        self.pgsqlFormWidget.setVisible(False)
        self.pgsqlConnectionsBox.setModel(PgsqlConnectionsModel())
        self.pgsqlSchemaBox.setCurrentText('gmlas')

        self.progressBar.setVisible(False)

    def showEvent(self, event):
        # Cannot do that in the constructor. The project is not fully setup when
        # it is called
        if not self.srsSelectionWidget.crs().isValid():
            self.srsSelectionWidget.setCrs(iface.mapCanvas().mapSettings().destinationCrs())
        BASE.showEvent(self, event)

    @pyqtSlot()
    def on_gmlasConfigButton_clicked(self):
        cur_dir = os.path.dirname(self.gmlasConfigLineEdit.text())
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Open GMLAS config file"),
            cur_dir,
            self.tr("XML Files (*.xml)"))
        if path:
            self.gmlasConfigLineEdit.setText(path)

    def gmlas_datasource(self):
        gmlasconf = self.gmlasConfigLineEdit.text()
        return gdal.OpenEx("GMLAS:{}".format(self.parent().parent().gml_path()),
                           open_options=['CONFIG_FILE={}'.format(gmlasconf),
                                         'EXPOSE_METADATA_LAYERS=YES'])
                                         # 'VALIDATE=YES'])

    @pyqtSlot()
    def on_validateButton_clicked(self):
        self.setCursor(Qt.WaitCursor)
        try:
            self.validate()
        finally:
            self.unsetCursor()

    def validate(self):
        data_source = self.gmlas_datasource() 

        if data_source is None:
            QMessageBox.critical(self, 'GMLAS', 'Impossible to open file using GMLAS driver')
            return

        '''
        metadata_layer = data_source.GetLayerByName('_ogr_layers_metadata')
        self.datasetsListWidget.clear()
        for feature in metadata_layer:
            layer_name = feature.GetField("layer_name")
            self.datasetsListWidget.addItem(layer_name)
 
            layer = data_source.GetLayerByName(layer_name)
            if layer is not None:
                feature_count = layer.GetFeatureCount()
                self.datasetsListWidget.addItem("{} ({})".format(layer_name, feature_count))
            else:
                
        layer_name
        layer_xpath
        layer_category TOP_LEVEL_ELEMENT, NESTED_ELEMENT or JUNCTION_TABLE
        layer_documentation
        '''

        self.datasetsListWidget.clear()
        for i in range(0, data_source.GetLayerCount()):
            layer = data_source.GetLayer(i)
            layer_name = layer.GetName()

            feature_count = layer.GetFeatureCount()
            print("{} ({})".format(layer_name, feature_count))

            self.datasetsListWidget.addItem(layer_name)

    def layers(self):
        layers = []
        for item in self.datasetsListWidget.selectedItems():
            layers.append(item.text())
        return layers
        return ','.join(layers)

    @pyqtSlot(bool)
    def on_sqliteRadioButton_toggled(self, checked):
        print('on_sqliteRadioButton_toggled')
        self.sqliteFormWidget.setVisible(self.sqliteRadioButton.isChecked())

    @pyqtSlot(bool)
    def on_pgsqlRadioButton_toggled(self, checked):
        print('on_pgsqlRadioButton_toggled')
        self.pgsqlFormWidget.setVisible(self.pgsqlRadioButton.isChecked())

    @pyqtSlot()
    def on_sqlitePathButton_clicked(self):
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Save to sqlite database"),
            data_folder,
            self.tr("SQLite Files (*.sqlite)"))
        if path:
            self.sqlitePathLineEdit.setText(path)

    @pyqtSlot(str)
    def on_pgsqlConnectionsBox_currentIndexChanged(self, text):
        if self.pgsqlConnectionsBox.currentIndex() == -1:
            self._pgsql_db = None
        else:
            self._pgsql_db = GeoDB.from_name(self.pgsqlConnectionsBox.currentText())

    def dst_datasource_name(self):
        if self.sqliteRadioButton.isChecked():
            return self.sqlitePathLineEdit.text()
        if self.pgsqlRadioButton.isChecked():
            return 'PG:{}'.format(self._pgsql_db.uri.connectionInfo(True))

    def dataset_creation_options(self):
        if self.sqliteRadioButton.isChecked():
            return ['SPATIALITE=YES']

    def layer_creation_options(self):
        options = []
        if self.pgsqlRadioButton.isChecked():
            options.append('SCHEMA={}'.format(self.pgsqlSchemaBox.currentText() or 'public'))
        return options

    def format(self):
        if self.sqliteRadioButton.isChecked():
            return 'SQLite'
        if self.pgsqlRadioButton.isChecked():
            return "PostgreSQL"

    def accessMode(self):
        if self.updateRadioButton.isChecked():
            return "update"
        if self.appendRadioButton.isChecked():
            return "append"
        if self.overwriteRadioButton.isChecked():
            return "overwrite"

    def dest_srs(self):
        srs = osr.SpatialReference()
        srs.ImportFromWkt(self.srsSelectionWidget.crs().toWkt())
        assert srs.Validate() == 0
        return srs

    @pyqtSlot()
    def on_importButton_clicked(self):
        self.progressBar.setValue(0)
        self.progressBar.setVisible(True)
        self.setCursor(Qt.WaitCursor)
        try:
            self.do_import()
        finally:
            self.progressBar.setVisible(False)
            self.unsetCursor()

    def import_callback(self, **kwargs):
        print('convert_callback: {}'.format(kwargs))

    def import_callback_data(self, **kwargs):
        print('convert_callback_data: {}'.format(kwargs))

    def do_import(self):
        params = {
            'destNameOrDestDS': self.dst_datasource_name(),
            'srcDS': self.gmlas_datasource(),
            'format': self.format(),
            'accessMode': self.accessMode(),
            'datasetCreationOptions': self.dataset_creation_options(),
            'layerCreationOptions': self.layer_creation_options(),
            'dstSRS': self.dest_srs(),
            'reproject': True
        }
        if self.bboxGroupBox.isChecked():
            # TODO: reproject bbox in source SRS
            params['spatFilter'] = self.bboxWidget.value()

        QgsMessageLog.logMessage("gdal.VectorTranslate({})".format(str(params)), 'GDAL')
        res = gdal.VectorTranslate(**params)
        QgsMessageLog.logMessage(str(res), 'GDAL')
