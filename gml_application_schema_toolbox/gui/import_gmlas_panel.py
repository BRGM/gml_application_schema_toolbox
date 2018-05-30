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

from qgis.utils import iface
from qgis.PyQt.QtCore import (
    Qt, QUrl, pyqtSlot, QFile,  QIODevice,
    QEventLoop)
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog, QListWidgetItem, QApplication
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt import uic

from gml_application_schema_toolbox import name as plugin_name
from gml_application_schema_toolbox.core.logging import log
from gml_application_schema_toolbox.core.proxy import qgis_proxy_settings
from ..core.load_gmlas_in_qgis import import_in_qgis
from gml_application_schema_toolbox.core.settings import settings
from gml_application_schema_toolbox.gui import InputError
from gml_application_schema_toolbox.gui.gmlas_panel_mixin import GmlasPanelMixin
from .xml_dialog import XmlDialog

from qgis.core import QgsMessageLog

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'import_gmlas_panel.ui'))

gdal.UseExceptions()


class ImportGmlasPanel(BASE, WIDGET, GmlasPanelMixin):

    def __init__(self, parent=None, gml_path=None):
        super(ImportGmlasPanel, self).__init__(parent)
        self.setupUi(self)
        self.databaseWidget.set_accept_mode(QFileDialog.AcceptSave)

        self.gmlasConfigLineEdit.setText(settings.value('default_gmlas_config'))
        self.acceptLanguageHeaderInput.setText(settings.value('default_language'))
        self.set_access_mode(settings.value('default_access_mode'))

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
        if path == '':
            raise InputError(self.tr("You must select a GMLAS config file"))

        xmlConfig = etree.parse(self.gmlasConfigLineEdit.text())

        # Set parameters
        c = xmlConfig.getroot()

        for l in c.iter('ExposeMetadataLayers'):
            l.text = str(self.ogrExposeMetadataLayersCheckbox.isChecked()).lower()
        for l in c.iter('LayerBuildingRules'):
            for n in l.iter('RemoveUnusedLayers'):
                n.text = str(self.ogrRemoveUnusedLayersCheckbox.isChecked()).lower()
            for n in l.iter('RemoveUnusedFields'):
                n.text = str(self.ogrRemoveUnusedFieldsCheckbox.isChecked()).lower()

        for l in c.findall("XLinkResolution/URLSpecificResolution/HTTPHeader"):
            name = l.find('Name').text
            if name == 'Accept-Language':
                l.find('Value').text = self.acceptLanguageHeaderInput.text()

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
        datasourceFile = self.gml_path()
        if datasourceFile == '':
            raise InputError(self.tr("You must select a input file or URL"))
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
        gdal.SetConfigOption('GDAL_HTTP_UNSAFESSL', 'YES')
        gdal.SetConfigOption('GDAL_HTTP_USERAGENT', settings.value('http_user_agent', plugin_name()))

        with qgis_proxy_settings():
            return gdal.OpenEx(driverConnection,
                               open_options=openOptions)

    @pyqtSlot()
    def on_loadLayersButton_clicked(self):
        #self.parent.on_downloadButton_clicked()
        self.setCursor(Qt.WaitCursor)
        try:
            self.validate()
        except InputError as e:
            e.show()
        finally:
            self.unsetCursor()

    def validate(self):
        #self.layerList.setTitle('Layers')
        data_source = self.gmlas_datasource() 

        if data_source is None:
            QMessageBox.critical(self,
                                 plugin_name(),
                                 self.tr('Failed to open file using OGR GMLAS driver'))
            return

        ogrMetadataLayerPrefix = '_ogr_'

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
        #self.layerList.setTitle('{} layer(s) found:'.format(self.datasetsListWidget.count()))


    def selected_layers(self):
        layers = []
        for item in self.datasetsListWidget.selectedItems():
            layers.append(item.data(Qt.UserRole))
        return layers

    def dataset_creation_options(self):
        if self.databaseWidget.format() == 'SQLite':
            return ['SPATIALITE=YES']

    def layer_creation_options(self):
        options = []
        if self.databaseWidget.format() == 'PostgreSQL':
            schema = self.databaseWidget.schema(create=True)
            options.append('SCHEMA={}'.format(schema or 'public'))
            if self.access_mode() == 'overwrite':
                options.append('OVERWRITE=YES')
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
            options.append('-forceNullable')
        if self.skipFailuresCheckbox.isChecked():
            options.append('-skipfailures')
        return options

    def import_params(self, dest):
        params = {
            'destNameOrDestDS': dest,
            'srcDS': self.gmlas_datasource(),
            'format': self.databaseWidget.format(),
            'accessMode': self.access_mode(),
            'datasetCreationOptions': self.dataset_creation_options(),
            'layerCreationOptions': self.layer_creation_options(),
            'options': self.translate_options()
        }
        if self.reprojectCheck.isChecked():
            params['reproject'] = True
            params['dstSRS'] = self.dest_srs()
        else:
            params['reproject'] = False
        if self.sourceSrsCheck.isChecked():
            params['srcSRS'] = self.src_srs()
            
        if self.convertToLinearCheckbox.isChecked():
             params['geometryType'] = 'CONVERT_TO_LINEAR'

        layers = self.selected_layers()
        if len(layers) > 0:
            params['layers'] = self.selected_layers()
            if self.ogrExposeMetadataLayersCheckbox.isChecked():
                params['layers'] = params['layers'] + [
                    '_ogr_fields_metadata',
                    '_ogr_layer_relationships',
                    '_ogr_layers_metadata',
                    '_ogr_other_metadata']

        if self.gmlas_bbox_group.isChecked():
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

    def do_load(self, append_to_db = None, append_to_schema = None):
        gdal.SetConfigOption("OGR_SQLITE_SYNCHRONOUS", "OFF")
        gdal.SetConfigOption('GDAL_HTTP_UNSAFESSL', 'YES')
        gdal.SetConfigOption('GDAL_HTTP_USERAGENT', settings.value('http_user_agent', plugin_name()))

        def error_handler(err, err_no, msg):
            if err >= gdal.CE_Warning:
                QgsMessageLog.logMessage("{} {}: {}".format(err, err_no, msg), plugin_name())

        if append_to_db is None:
            dest = self.databaseWidget.datasource_name()
            if dest == '' and self.databaseWidget.format() == "SQLite":
                with tempfile.NamedTemporaryFile(suffix='.sqlite') as tmp:
                    dest = tmp.name
                    QgsMessageLog.logMessage("Temp SQLITE: {}".format(dest), plugin_name())

            if dest.startswith('PG:'):
                schema = self.databaseWidget.schema()
            else:
                schema = None
            db_format = self.databaseWidget.format()
            params = self.import_params(dest)
        else:
            schema = append_to_schema
            db_format = "PostgreSQL" if append_to_db.startswith("PG:") else "SQLite"
            params = self.import_params(append_to_db)
            # force append
            params["accessMode"] = "append"

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            gdal.PushErrorHandler(error_handler)
            self.translate(params)
            if append_to_db is None:
                import_in_qgis(dest, db_format, schema)
            
        except InputError as e:
            e.show()
        except RuntimeError as e:
            QMessageBox.warning(None,
                                plugin_name(),
                                e.args[0])
        finally:
            QApplication.restoreOverrideCursor()
            gdal.PopErrorHandler()

