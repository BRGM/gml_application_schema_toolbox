#! python3  # noqa: E265

"""
/***************************************************************************
 GmlasPanelMixin
                                 A QGIS plugin
 GMLAS Plugin
                             -------------------
        begin                : 2016-12-09
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
# 3rd party
from osgeo import gdal

# PyQGIS
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QEventLoop, Qt, pyqtSlot
from qgis.PyQt.QtWidgets import QFileDialog, QProgressDialog

# project package
from gml_application_schema_toolbox.__about__ import __title__
from gml_application_schema_toolbox.core.log_handler import PluginLogHandler
from gml_application_schema_toolbox.core.proxy import qgis_proxy_settings

# ############################################################################
# ########## Classes ###############
# ##################################


class GmlasPanelMixin:
    def __init__(self):
        # map to the plugin log handler
        self.plg_logger = PluginLogHandler()

    @pyqtSlot()
    def on_gmlasConfigButton_clicked(self):
        path, filter = QFileDialog.getOpenFileName(
            self,
            self.tr("Open GMLAS config file"),
            self.gmlasConfigLineEdit.text(),
            self.tr("XML Files (*.xml)"),
        )
        if path:
            self.gmlasConfigLineEdit.setText(path)

    def translate(self, params):
        if params is None:
            return
        params["callback"] = self.translate_callback

        dlg = QProgressDialog(self)
        dlg.setWindowTitle(__title__)
        dlg.setLabelText("Operation in progress")
        dlg.setMinimum(0)
        dlg.setMaximum(100)
        dlg.setWindowModality(Qt.WindowModal)
        self.progress_dlg = dlg

        self.setCursor(Qt.WaitCursor)
        try:
            self.plg_logger.log("gdal.VectorTranslate({})".format(str(params)))
            gdal.PushErrorHandler(self.plg_logger.gdal_error_handler)
            with qgis_proxy_settings():
                res = gdal.VectorTranslate(**params)
            gdal.PopErrorHandler()
            self.plg_logger.log(str(res))
        finally:
            self.unsetCursor()
            self.progress_dlg.reset()
            self.progress_dlg = None

    def translate_callback(self, pct, msg, user_data):
        self.progress_dlg.setValue(int(100 * pct))
        QgsApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        if self.progress_dlg.wasCanceled():
            return 0
        return 1
