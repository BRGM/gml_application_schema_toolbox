#!/usr/bin/env python

#   Copyright (C) 2016 BRGM (http:///brgm.fr)
#   Copyright (C) 2016 Oslandia <infos@oslandia.com>
#
#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Library General Public
#   License as published by the Free Software Foundation; either
#   version 2 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Library General Public License for more details.
#   You should have received a copy of the GNU Library General Public
#   License along with this library; if not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
from __future__ import absolute_import
from builtins import str
from builtins import range
from builtins import object
# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.PyQt.QtXml import *
from qgis.core import *
from qgis.gui import *

from .core.load_gmlas_in_qgis import import_in_qgis
from .gui.database_widget import DatabaseWidget
from .gui import InputError
from .gui.xml_custom_widget import XMLWidgetFactory, XMLWidgetFormatter

import os
import sqlite3


package_path = [os.path.join(os.path.dirname(__file__), "extlibs")]
import sys
if not set(package_path).issubset(set(sys.path)):
    sys.path = package_path + sys.path

from . import name as plugin_name
from . import version as plugin_version

#from .gui.dockwidget import DockWidget
from .gui.settings_dialog import SettingsDialog
from .gui.export_gmlas_panel import ExportGmlasPanel

from .gui.load_wizard import LoadWizard

# global iface
g_iface = None

def get_iface():
    return g_iface

class MainPlugin(object):

    def __init__(self, iface):
        self.iface = iface
        global g_iface
        g_iface = iface

    def initGui(self):
        self.settingsAction = QAction("Settings", self.iface.mainWindow())
        self.settingsAction.triggered.connect(self.onSettings)

        self.aboutAction = QAction("About", self.iface.mainWindow())
        self.aboutAction.triggered.connect(self.onAbout)

        self.helpAction = QAction("Help", self.iface.mainWindow())
        self.helpAction.triggered.connect(self.onHelp)

        self.loadAction = QAction("Load a GMLAS database", self.iface.mainWindow())
        self.loadAction.triggered.connect(self.onLoad)

        self.exportAction = QAction("Export a GMLAS database to GML", self.iface.mainWindow())
        self.exportAction.triggered.connect(self.onExport)

        self.wizardAction = QAction("Load (wizard)", self.iface.mainWindow())
        self.wizardAction.triggered.connect(self.onWizardLoad)

        self.iface.addPluginToMenu(plugin_name(), self.wizardAction)
        self.iface.addPluginToMenu(plugin_name(), self.loadAction)
        self.iface.addPluginToMenu(plugin_name(), self.exportAction)
        self.iface.addPluginToMenu(plugin_name(), self.settingsAction)
        self.iface.addPluginToMenu(plugin_name(), self.aboutAction)
        self.iface.addPluginToMenu(plugin_name(), self.helpAction)

        self.model_dlg = None
        self.model = None

        self.xml_widget_factory = XMLWidgetFactory()
        self.xml_widget_formatter = XMLWidgetFormatter()
        QgsGui.editorWidgetRegistry().registerWidget("XML", self.xml_widget_factory)
        QgsApplication.fieldFormatterRegistry().addFieldFormatter(self.xml_widget_formatter)

    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(plugin_name(), self.wizardAction)
        self.iface.removePluginMenu(plugin_name(), self.loadAction)
        self.iface.removePluginMenu(plugin_name(), self.exportAction)
        self.iface.removePluginMenu(plugin_name(), self.settingsAction)
        self.iface.removePluginMenu(plugin_name(), self.aboutAction)
        self.iface.removePluginMenu(plugin_name(), self.helpAction)

    def onAbout(self):
        self.about_dlg = QWidget()
        vlayout = QVBoxLayout()
        l = QLabel(u"""
        <h1>QGIS GML Application Schema Toolbox</h1>
        <h3>Version: {}</h3>
        <p>This plugin is a prototype aiming at experimenting with the manipulation of "Complex Features" streams.</p>
        <p>Two modes are available:
        <ul><li>A mode where the initial XML hierarchical view is preserved. In this mode, an XML instance
        is represented by a unique QGIS vector layer with a column that stores the XML subtree for each feature.
        Augmented tools are available to identify a feature or display the attribute table of the layer.
        Custom QT-based viewers can be run on XML elements of given types.</li>
        <li>A mode where the XML hierarchical data is first converted to a relational database (SQlite).
        In this mode, the data is spread accross different QGIS layers. Links between tables are declared
        as QGIS relations and "relation reference" widgets. It then allows to use the standard QGIS attribute
        table (in "forms" mode) to navigate the relationel model.</li>
        </ul>
        <p>This plugin has been funded by BRGM and developed by Oslandia.</p>
        """.format(plugin_version()))
        l.setWordWrap(True)
        vlayout.addWidget(l)
        hlayout = QHBoxLayout()
        l2 = QLabel()
        l2.setPixmap(QPixmap(os.path.join(os.path.dirname(__file__), "logo_brgm.svg")).scaledToWidth(200, Qt.SmoothTransformation))
        l3 = QLabel()
        l3.setPixmap(QPixmap(os.path.join(os.path.dirname(__file__), "logo_oslandia.png")).scaledToWidth(200, Qt.SmoothTransformation))
        hlayout.addWidget(l2)
        hlayout.addWidget(l3)
        vlayout.addLayout(hlayout)
        self.about_dlg.setLayout(vlayout)
        self.about_dlg.setWindowTitle(plugin_name())
        self.about_dlg.setWindowModality(Qt.WindowModal)
        self.about_dlg.show()
        self.about_dlg.resize(600,600)
        
    def onSettings(self):
        dlg = SettingsDialog()
        dlg.exec_()

    def onHelp(self):
        url = 'https://github.com/BRGM/gml_application_schema_toolbox/blob/master/README.md'
        QDesktopServices.openUrl(QUrl(url))

    def onLoad(self):
        dlg = QDialog(self.iface.mainWindow())
        dlg.setWindowTitle("Choose the database to load layers from")
        layout = QVBoxLayout()
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dlg.accept)
        button_box.rejected.connect(dlg.reject)
        db_widget = DatabaseWidget(dlg, is_input=True)
        layout.addWidget(db_widget)
        layout.addWidget(button_box)
        dlg.setLayout(layout)
        if dlg.exec_() == QDialog.Rejected:
            return

        try:
            source = db_widget.datasource_name()
            if source.startswith('PG:'):
                schema = db_widget.schema()
            else:
                schema = None
            QApplication.setOverrideCursor(Qt.WaitCursor)
            import_in_qgis(source, db_widget.format(), schema)
        except InputError as e:
            QMessageBox.warning(None,
                                "Error during layer loading",
                                e.args[0])
        except RuntimeError as e:
            QMessageBox.warning(None,
                                "Error during layer loading",
                                e.args[0])
        finally:
            QApplication.restoreOverrideCursor()
        

    def onWizardLoad(self):
        self.wizard = LoadWizard(self.iface.mainWindow())
        self.wizard.setModal(False)
        self.wizard.show()
        self.wizard.resize(500,500)
        self.wizard.finished.connect(self.onWizardEnd)
    def onWizardEnd(self, result):
        # destruct the object
        # (this makes sure collapsible states are correctly saved)
        self.wizard.setParent(None)
        self.wizard.deleteLater()
        
    def onExport(self):
        w = ExportGmlasPanel(self.iface.mainWindow())
        w.exec_()
