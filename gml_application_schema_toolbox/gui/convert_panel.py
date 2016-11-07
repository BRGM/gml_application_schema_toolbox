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
from osgeo import gdal

from qgis.PyQt.QtCore import QSettings, Qt, QUrl, pyqtSlot, QFile, QIODevice, QAbstractItemModel, QModelIndex
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt import uic

from processing.tools.postgis import GeoDB

from .xml_dialog import XmlDialog

gmlasconf = os.path.join(os.path.dirname(__file__),
                         '..', 'conf', 'gmlasconf.xml')

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'convert_panel.ui'))


data_folder = '/home/qgis/qgisgmlas/data'

gdal.UseExceptions()


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


class ConvertPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(ConvertPanel, self).__init__(parent)
        self.setupUi(self)

        self.pgsqlFormWidget.setVisible(False)
        self.convertProgressBar.setVisible(False)

        self.pgsqlConnectionsBox.setModel(PgsqlConnectionsModel())
        self.pgsqlSchemaBox.setCurrentText('gmlas')

        self.gmlPathLineEdit.setText('/home/qgis/qgisgmlas/data/geosciml/mappedfeature.gml')
        self.sqlitePathLineEdit.setText('/home/qgis/qgisgmlas/data/test.sqlite')

    @pyqtSlot()
    def on_gmlPathButton_clicked(self):
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Open GML file"),
            data_folder,
            self.tr("GML Files (*.gml *.xml)"))
        if path:
            self.gmlPathLineEdit.setText(path)

    @pyqtSlot()
    def on_getCapabilitiesButton_clicked(self):
        XmlDialog(self, self.wfs().getcapabilities().read()).exec_()
        #url = WFSCapabilitiesReader().capabilities_url(self.uri())
        #QDesktopServices.openUrl(QUrl(url))

    def gmlas_datasource_name(self):
        return "GMLAS:{}".format(self.gmlPathLineEdit.text())

    def gmlas_datasource(self):
        return gdal.OpenEx("GMLAS:{}".format(self.gmlPathLineEdit.text()),
                           open_options=['CONFIG_FILE={}'.format(gmlasconf),
                                         'EXPOSE_METADATA_LAYERS=YES',
                                         'VALIDATE=YES'])

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

    @pyqtSlot()
    def on_convertButton_clicked(self):
        self.convertProgressBar.setValue(0)
        self.convertProgressBar.setVisible(True)
        self.setCursor(Qt.WaitCursor)
        try:
            self.convert(
                destNameOrDestDS=self.dst_datasource_name(),
                srcDS=self.gmlas_datasource(),
                format=self.format(),
                accessMode=self.accessMode(),
                datasetCreationOptions=self.dataset_creation_options(),
                layerCreationOptions=self.layer_creation_options())
        finally:
            self.convertProgressBar.setVisible(False)
            self.unsetCursor()

    def convert_callback(self, **kwargs):
        print('convert_callback: {}'.format(kwargs))

    def convert_callback_data(self, **kwargs):
        print('convert_callback_data: {}'.format(kwargs))

    def convert(self, **kwargs):
        print(kwargs)
        res = gdal.VectorTranslate(**kwargs)
        print(res)
