# -*- coding: utf-8 -*-
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

import os
from osgeo import gdal, osr

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt, pyqtSlot, QEventLoop
from qgis.PyQt.QtWidgets import QFileDialog, QProgressDialog

from gml_application_schema_toolbox import name as plugin_name
from gml_application_schema_toolbox.core.logging import log, gdal_error_handler


class GmlasPanelMixin():

    @pyqtSlot()
    def on_gmlasConfigButton_clicked(self):
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Open GMLAS config file"),
            self.gmlasConfigLineEdit.text(),
            self.tr("XML Files (*.xml)"))
        if path:
            self.gmlasConfigLineEdit.setText(path)

    def translate(self, params):
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
