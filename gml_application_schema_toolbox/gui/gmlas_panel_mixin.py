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
from gml_application_schema_toolbox.core.proxy import qgis_proxy_settings
from gml_application_schema_toolbox.toolbelt.log_handler import PlgLogger

# ############################################################################
# ########## Classes ###############
# ##################################


class GmlasPanelMixin:
    def __init__(self):
        # map to the plugin log handler
        self.plg_logger = PlgLogger()

    @pyqtSlot()
    def on_gmlasConfigButton_clicked(self):
        filepath, suffix_filter = QFileDialog.getOpenFileName(
            parent=self,
            caption=self.tr("Open GMLAS config file"),
            directory=self.gmlasConfigLineEdit.text(),
            filter=self.tr("XML Files (*.xml)"),
        )
        if filepath:
            self.gmlasConfigLineEdit.setText(filepath)

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
