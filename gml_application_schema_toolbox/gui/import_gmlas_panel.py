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
import tempfile

from io import BytesIO

from owslib.etree import etree

from osgeo import gdal, osr

from qgis.core import QgsApplication
from qgis.utils import iface
from qgis.PyQt.QtCore import (
    QSettings, Qt, QUrl, pyqtSlot, QFile, QIODevice,
    QAbstractItemModel, QModelIndex,
    QEventLoop)
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog, QProgressDialog
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt import uic

from processing.tools.postgis import GeoDB

from gml_application_schema_toolbox import name as plugin_name
from gml_application_schema_toolbox.core.logging import log, gdal_error_handler
from .xml_dialog import XmlDialog

DEFAULT_GMLAS_CONF = os.path.realpath(os.path.join(os.path.dirname(__file__),
                                      '..', 'conf', 'gmlasconf.xml'))

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'import_gmlas_panel.ui'))


data_folder = '~'

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

        self.gmlPathLineEdit.setText('/home/qgis/qgisgmlas/data/geosciml/mappedfeature.gml')
        self.gmlasConfigLineEdit.setText(DEFAULT_GMLAS_CONF)

        self._pgsql_db = None
        self.pgsqlFormWidget.setVisible(False)
        self.pgsqlConnectionsBox.setModel(PgsqlConnectionsModel())
        self.pgsqlConnectionsRefreshButton.setIcon(
            QgsApplication.getThemeIcon('/mActionRefresh.png'))

    @pyqtSlot(str)
    def set_gml_path(self, path):
        self._gml_path = path

    def showEvent(self, event):
        # Cannot do that in the constructor. The project is not fully setup when
        # it is called
        if not self.srsSelectionWidget.crs().isValid():
            self.srsSelectionWidget.setCrs(iface.mapCanvas().mapSettings().destinationCrs())
        BASE.showEvent(self, event)

    @pyqtSlot()
    def on_gmlPathButton_clicked(self):
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Open GML file"),
            data_folder,
            self.tr("GML files or XSD (*.gml *.xml *.xsd)"))
        if path:
            self.gmlPathLineEdit.setText(path)

    @pyqtSlot()
    def on_gmlasConfigButton_clicked(self):
        cur_dir = os.path.dirname(self.gmlasConfigLineEdit.text())
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Open GMLAS config file"),
            cur_dir,
            self.tr("XML Files (*.xml)"))
        if path:
            self.gmlasConfigLineEdit.setText(path)


    # Read XML file and substitute form parameters
    def gmlas_config(self):
        xmlConfig = etree.parse(self.gmlasConfigLineEdit.text())

        # Set parameters
        c = xmlConfig.getroot()
        for l in c.iter('ExposeMetadataLayers'):
            l.text = str(self.ogrExposeMetadataLayersCheckbox.isChecked()).lower()
        for l in c.iter("LayerBuildingRules/RemoveUnusedLayers"):
            l.text = str(self.ogrRemoveUnusedLayersCheckbox.isChecked()).lower()
        for l in c.iter("LayerBuildingRules/RemoveUnusedFields"):
            l.text = str(self.ogrRemoveUnusedFieldsCheckbox.isChecked()).lower()

        for l in c.iter("XLinkResolution/URLSpecificResolution/HTTPHeader[Name = 'Accept-Language']/Value"):
            l.text = self.acceptLanguageHeaderInput.text()

        textConfig = BytesIO()
        xmlConfig.write(textConfig, encoding='utf-8', xml_declaration=False)

        # Write config in temp file
        tf = tempfile.NamedTemporaryFile(prefix='gmlasconf_', suffix='.xml', delete=False)
        tf.write(textConfig.getvalue())
        tf.close()
        log("Temporary configuration file created '{}' for conversion.".format(str(tf.name)))

        return tf.name

    def gmlas_datasource(self):
        gmlasconf = self.gmlas_config()
        datasourceFile = self.gmlPathLineEdit.text()
        isXsd = datasourceFile.endswith(".xsd")
        isUrl = datasourceFile.startswith("http")
        swapCoordinates = self.swapCoordinatesCombo.currentText()
        driverConnection = ""
        openOptions = ['EXPOSE_METADATA_LAYERS=YES', 'CONFIG_FILE={}'.format(gmlasconf)]

        openOptions.append('SWAP_COORDINATES={}'.format(swapCoordinates))

        if isXsd:
            driverConnection = "GMLAS:"
            openOptions.append('XSD={}'.format(datasourceFile))
        elif isUrl:
            driverConnection = "GMLAS:/vsicurl_streaming/{}".format(datasourceFile)
        else:
            driverConnection = "GMLAS:{}".format(datasourceFile)

        return gdal.OpenEx(driverConnection,
                           open_options=openOptions)

    @pyqtSlot()
    def on_validateButton_clicked(self):
        self.setCursor(Qt.WaitCursor)
        try:
            self.validate()
        finally:
            self.unsetCursor()

    def validate(self):
        self.layerList.setTitle('Layers')
        data_source = self.gmlas_datasource() 

        if data_source is None:
            QMessageBox.critical(self, 'GMLAS', 'Failed to open file using OGR GMLAS driver')
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
        ogrMetadataLayerPrefix = '_ogr_'

        self.datasetsListWidget.clear()
        for i in range(0, data_source.GetLayerCount()):
            layer = data_source.GetLayer(i)
            layer_name = layer.GetName()
            if not layer_name.startswith(ogrMetadataLayerPrefix): 
              feature_count = layer.GetFeatureCount()

              from qgis.PyQt.QtWidgets import QListWidgetItem
              item = QListWidgetItem("{} ({})".format(layer_name, feature_count))
              item.setData(Qt.UserRole, layer_name)
              self.datasetsListWidget.addItem(item)

        self.datasetsListWidget.sortItems()
        self.datasetsListWidget.selectAll()
        self.layerList.setTitle('{} layer(s) found:'.format(self.datasetsListWidget.count()))


    def selected_layers(self):
        layers = []
        for item in self.datasetsListWidget.selectedItems():
            layers.append(item.data(Qt.UserRole))
        return layers



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
        current_path = self.sqlitePathLineEdit.text()
        cur_dir = os.path.dirname(current_path) if current_path else ''
        path, filter = QFileDialog.getSaveFileName(self,
            self.tr("Save to sqlite database"),
            cur_dir,
            self.tr("SQLite Files (*.sqlite)"))
        if path:
            if os.path.splitext(path)[1] == '':
                path = '{}.sqlite'.format(path)
            self.sqlitePathLineEdit.setText(path)

    @pyqtSlot(str)
    def on_pgsqlConnectionsBox_currentIndexChanged(self, text):
        if self.pgsqlConnectionsBox.currentIndex() == -1:
            self._pgsql_db = None
        else:
            self._pgsql_db = GeoDB.from_name(self.pgsqlConnectionsBox.currentText())

        self.pgsqlSchemaBox.clear()
        schemas = sorted([schema[1] for schema in self._pgsql_db.list_schemas()])
        for schema in schemas:
            self.pgsqlSchemaBox.addItem(schema)

    @pyqtSlot()
    def on_pgsqlConnectionsRefreshButton_clicked(self):
        self.pgsqlConnectionsBox.setModel(PgsqlConnectionsModel())

    def dst_datasource_name(self):
        if self.sqliteRadioButton.isChecked():
            path = self.sqlitePathLineEdit.text()
            if path == '':
                QMessageBox.warning(self,
                                    plugin_name(),
                                    "You must select a SQLite file")
                return None
            return path
        if self.pgsqlRadioButton.isChecked():
            if self._pgsql_db is None:
                QMessageBox.warning(self,
                                    plugin_name(),
                                    "You must select a PostgreSQL connection")
                return None
            return 'PG:{}'.format(self._pgsql_db.uri.connectionInfo(True))

    def dataset_creation_options(self):
        if self.sqliteRadioButton.isChecked():
            return ['SPATIALITE=YES']

    def layer_creation_options(self):
        options = []
        if self.pgsqlRadioButton.isChecked():
            schema = self.pgsqlSchemaBox.currentText()

            #if self.pgsqlSchemaBox.currentIndex() == -1:
            schemas = [schema[1] for schema in self._pgsql_db.list_schemas()]
            if not schema in schemas:
                res = QMessageBox.question(self,
                                           plugin_name(),
                                           self.tr('Create schema "{}" ?').
                                           format(schema))
                if res != QMessageBox.Ok:
                    return False
                self._pgsql_db.create_schema(schema)
            options.append('SCHEMA={}'.format(schema or 'public'))
            if self.accessMode() == 'overwrite':
                options.append('OVERWRITE=YES')
        return options

    def format(self):
        if self.sqliteRadioButton.isChecked():
            return 'SQLite'
        if self.pgsqlRadioButton.isChecked():
            return "PostgreSQL"

    def accessMode(self):
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
        srs.ImportFromWkt(self.srsSelectionWidget.crs().toWkt())
        assert srs.Validate() == 0
        return srs

    def translate_options(self):
        options = []
        if not self.forceNullableCheckbox.isChecked():
            options.append('-forceNullable')
        if self.skipFailuresCheckbox.isChecked():
            options.append('-skipfailures')
        return options

    def import_params(self):
        dst_datasource_name = self.dst_datasource_name()
        if not dst_datasource_name:
            return None

        params = {
            'destNameOrDestDS': dst_datasource_name,
            'srcDS': self.gmlas_datasource(),
            'format': self.format(),
            'accessMode': self.accessMode(),
            'datasetCreationOptions': self.dataset_creation_options(),
            'layerCreationOptions': self.layer_creation_options(),
            'dstSRS': self.dest_srs(),
            'reproject': True,
            'options': self.translate_options(),
            'callback': self.import_callback
        }
        if self.convertToLinearCheckbox.isChecked():
             params['geometryType'] = 'CONVERT_TO_LINEAR'

        layers = self.selected_layers()
        if len(layers) > 0:
            params['layers'] = self.selected_layers()

        if self.bboxGroupBox.isChecked():
            if self.bboxWidget.value() == '':
                QMessageBox.warning(self,
                                    plugin_name(),
                                    "Extent is empty")
                return
            if not self.bboxWidget.isValid():
                QMessageBox.warning(self,
                                    plugin_name(),
                                    "Extent is invalid")
                return
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
    def on_importButton_clicked(self):
        params = self.import_params()
        if params is None:
            return

        dlg = QProgressDialog(self)
        dlg.setWindowTitle(plugin_name())
        dlg.setLabelText('Operation in progress')
        dlg.setMinimum(0)
        dlg.setMaximum(100)
        dlg.setWindowModality(Qt.WindowModal)
        self.progress_dlg = dlg

        self.setCursor(Qt.WaitCursor)
        try:
            log("gdal.VectorTranslate({})".format(str(params)))
            gdal.PushErrorHandler(gdal_error_handler)
            res = gdal.VectorTranslate(**params)
            gdal.PopErrorHandler()
            log(str(res))
        finally:
            self.unsetCursor()
            self.progress_dlg.reset()
            self.progress_dlg = None

    def import_callback(self, pct, msg, user_data):
        self.progress_dlg.setValue(int(100*pct))
        QgsApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        if self.progress_dlg.wasCanceled():
            return 0
        return 1
