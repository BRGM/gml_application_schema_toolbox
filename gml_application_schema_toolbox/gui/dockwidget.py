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
from qgis.PyQt import uic
from gml_application_schema_toolbox.gui.download_wfs2_panel import DownloadWfs2Panel
from gml_application_schema_toolbox.gui.import_panel import ImportPanel
from gml_application_schema_toolbox.gui.export_gmlas_panel import ExportGmlasPanel
from gml_application_schema_toolbox.gui.help_panel import HelpPanel

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'dockwidget.ui'))


class DockWidget(BASE, WIDGET):

    def __init__(self, parent=None):
        super(DockWidget, self).__init__(parent)
        self.setupUi(self)

        self.download_panel = DownloadWfs2Panel()
        self.tabWidget.addTab(self.download_panel, self.tr('Download'))

        self.import_panel = ImportPanel()
        self.tabWidget.addTab(self.import_panel, self.tr('Convert'))

        self.export_panel = ExportGmlasPanel()
        self.tabWidget.addTab(self.export_panel, self.tr('Export'))

        self.help_panel = HelpPanel()
        self.tabWidget.addTab(self.help_panel, self.tr('Help'))

        self.download_panel.file_downloaded.connect(self.on_fileDownloaded)

    def on_fileDownloaded(self, path):
        self.import_panel.xml_panel.gmlPathLineEdit.setText(path)
        self.import_panel.gmlas_panel.gmlPathLineEdit.setText(path)
        self.tabWidget.setCurrentIndex(self.tabWidget.indexOf(self.import_panel))
