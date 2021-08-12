#! python3  # noqa: E265


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


# QGIS
from qgis.core import QgsApplication
from qgis.gui import QgsGui
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from qgis.utils import showPluginHelp

from gml_application_schema_toolbox.__about__ import (
    DIR_PLUGIN_ROOT,
    __title__,
    __version__,
)
from gml_application_schema_toolbox.core.load_gmlas_in_qgis import import_in_qgis
from gml_application_schema_toolbox.gui import InputError
from gml_application_schema_toolbox.gui.database_widget import DatabaseWidget
from gml_application_schema_toolbox.gui.export_gmlas_panel import ExportGmlasPanel
from gml_application_schema_toolbox.gui.load_wizard import LoadWizard
from gml_application_schema_toolbox.gui.xml_custom_widget import (
    XMLWidgetFactory,
    XMLWidgetFormatter,
)
from gml_application_schema_toolbox.resources.gui.dlg_settings import PlgOptionsFactory
from gml_application_schema_toolbox.toolbelt import PlgLogger

# ############################################################################
# ########## Globals ###############
# ##################################

# global iface
g_iface = None


def get_iface():
    return g_iface


# ############################################################################
# ########## Classes ###############
# ##################################


class GmlasPlugin(object):
    def __init__(self, iface):
        self.iface = iface
        self.log = PlgLogger().log
        global g_iface
        g_iface = iface

    def initGui(self):
        """Set up plugin UI elements."""

        # settings page within the QGIS preferences menu
        self.options_factory = PlgOptionsFactory()
        self.iface.registerOptionsWidgetFactory(self.options_factory)

        # -- Actions
        self.action_about = QAction(
            QIcon(str(DIR_PLUGIN_ROOT / "resources/images/info-circle.svg")),
            "About",
            self.iface.mainWindow(),
        )
        self.action_about.triggered.connect(self.onAbout)

        self.action_export = QAction(
            QIcon(QgsApplication.iconPath("mActionSharingExport.svg")),
            "Export a GMLAS database to GML",
            self.iface.mainWindow(),
        )
        self.action_export.triggered.connect(self.onExport)

        self.action_help = QAction(
            QIcon(":/images/themes/default/mActionHelpContents.svg"),
            "Help",
            self.iface.mainWindow(),
        )
        self.action_help.triggered.connect(lambda: showPluginHelp(filename="doc/index"))

        self.action_load = QAction(
            QIcon(QgsApplication.iconPath("mActionSharingImport.svg")),
            "Load a GMLAS database",
            self.iface.mainWindow(),
        )
        self.action_load.triggered.connect(self.onLoad)

        self.action_settings = QAction(
            QgsApplication.getThemeIcon("console/iconSettingsConsole.svg"),
            "Settings",
            self.iface.mainWindow(),
        )
        self.action_settings.triggered.connect(
            lambda: self.iface.showOptionsDialog(
                currentPage="mOptionsPage{}".format(__title__)
            )
        )

        self.action_wizard = QAction(
            QIcon(str(DIR_PLUGIN_ROOT / "resources/images/mActionAddGMLLayer.svg")),
            "Load (wizard)",
            self.iface.mainWindow(),
        )
        self.action_wizard.triggered.connect(self.onWizardLoad)

        # Model and custom XML widget
        self.model_dlg = None
        self.model = None

        self.xml_widget_factory = XMLWidgetFactory()
        self.xml_widget_formatter = XMLWidgetFormatter()
        QgsGui.editorWidgetRegistry().registerWidget("XML", self.xml_widget_factory)
        QgsApplication.fieldFormatterRegistry().addFieldFormatter(
            self.xml_widget_formatter
        )

        # -- Menu
        self.iface.addPluginToMenu(__title__, self.action_wizard)
        self.iface.addPluginToMenu(__title__, self.action_load)
        self.iface.addPluginToMenu(__title__, self.action_export)
        self.iface.addPluginToMenu(__title__, self.action_settings)
        self.iface.addPluginToMenu(__title__, self.action_about)
        self.iface.addPluginToMenu(__title__, self.action_help)

        # -- Toolbar
        self.iface.addToolBarIcon(self.action_wizard)

    def unload(self):
        """Cleans up when plugin is disabled/uninstalled."""
        # -- Clean up menu
        self.iface.removePluginMenu(__title__, self.action_wizard)
        self.iface.removePluginMenu(__title__, self.action_load)
        self.iface.removePluginMenu(__title__, self.action_export)
        self.iface.removePluginMenu(__title__, self.action_settings)
        self.iface.removePluginMenu(__title__, self.action_about)
        self.iface.removePluginMenu(__title__, self.action_help)

        # -- Clean up toolbar
        self.iface.removeToolBarIcon(self.action_wizard)

        # -- Clean up preferences panel in QGIS settings
        self.iface.unregisterOptionsWidgetFactory(self.options_factory)

        # remove actions
        del self.action_about
        del self.action_export
        del self.action_load
        del self.action_help
        del self.action_settings
        del self.action_wizard

    def onAbout(self):
        self.about_dlg = QWidget()
        vlayout = QVBoxLayout()
        lbl_about_main = QLabel(
            """
        <h1>{}</h1>
        <h3>Version: {}</h3>
        <p>This plugin is a prototype aiming at experimenting with the manipulation of <b>Complex Features</b> streams.</p>
        <p>Two modes are available:
        <ul><li>A mode where the <b>initial XML hierarchical view</b> is preserved. In this mode, an XML instance
        is represented by a unique QGIS vector layer with a column that stores the XML subtree for each feature.
        Augmented tools are available to identify a feature or display the attribute table of the layer.</li>
        <li>A mode where the XML hierarchical data is first <b>converted to a relational database</b>.
        In this mode, the data is spread accross different QGIS layers. Links between tables are declared
        as QGIS relations and "relation reference" widgets. It then allows to use the standard QGIS attribute
        table (in "forms" mode) to navigate the relationel model.</li>
        </ul>
        <p>Custom Qt-based viewers can be run on XML elements of given types.</p>

        <p>Teams involved in the development of the current plugin:
        <ul>
        <li><a href="http://www.oslandia.com">Oslandia</a> (current version of the QGIS plugin, and first proof of concept)</li>
        <li><a href="http://www.spatialys.com">Spatialys</a> (GMLAS driver in OGR)</li>
        <li><a href="http://www.camptocamp.com">camptocamp</a> (former version of the plugin)</li>
        </ul>
        </p>
        <p>Funders involved:
        <ul>
        <li><a href="http://www.brgm.fr">BRGM</a></li>
        <li><a href="https://www.eea.europa.eu/">European Environment Agency</a> (Copernicus funding)</li>
        <li><b>The Association of Finnish Local and Regional Authorities</b> (through <a href="http://www.gispo.fi">Gispo.fi</a>)</li>
        </ul>
        </p>
        """.format(
                __title__, __version__
            )
        )
        lbl_about_main.setWordWrap(True)
        vlayout.addWidget(lbl_about_main)
        hlayout = QHBoxLayout()
        hlayout2 = QHBoxLayout()
        lbl_logo_brgm = QLabel()
        lbl_logo_brgm.setPixmap(
            QPixmap(
                str(DIR_PLUGIN_ROOT / "resources/images/logo_brgm.svg")
            ).scaledToWidth(200, Qt.SmoothTransformation)
        )
        lbl_logo_eea = QLabel()
        lbl_logo_eea.setPixmap(
            QPixmap(
                str(DIR_PLUGIN_ROOT / "resources/images/logo_eea.png")
            ).scaledToWidth(200, Qt.SmoothTransformation)
        )
        lbl_logo_oslandia = QLabel()
        lbl_logo_oslandia.setPixmap(
            QPixmap(
                str(DIR_PLUGIN_ROOT / "resources/images/logo_oslandia.png")
            ).scaledToWidth(150, Qt.SmoothTransformation)
        )
        lbl_logo_spatialys = QLabel()
        lbl_logo_spatialys.setPixmap(
            QPixmap(
                str(DIR_PLUGIN_ROOT / "resources/images/logo_spatialys.png")
            ).scaledToWidth(100, Qt.SmoothTransformation)
        )
        lbl_logo_c2c = QLabel()
        lbl_logo_c2c.setPixmap(
            QPixmap(
                str(DIR_PLUGIN_ROOT / "resources/images/logo_c2c.svg")
            ).scaledToWidth(100, Qt.SmoothTransformation)
        )
        hlayout.addWidget(lbl_logo_brgm)
        hlayout.addWidget(lbl_logo_eea)
        vlayout.addLayout(hlayout)
        hlayout2.addWidget(lbl_logo_oslandia)
        hlayout2.addWidget(lbl_logo_spatialys)
        hlayout2.addWidget(lbl_logo_c2c)
        vlayout.addLayout(hlayout2)
        self.about_dlg.setLayout(vlayout)
        self.about_dlg.setWindowTitle(__title__)
        self.about_dlg.setWindowModality(Qt.WindowModal)
        self.about_dlg.show()
        self.about_dlg.resize(600, 800)

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

        # if dialog is closed or if no connection is selected
        dlg.setLayout(layout)
        if dlg.exec_() == QDialog.Rejected:
            return

        if not db_widget.selected_connection_name:
            return

        # if a connection is selected
        self.log(
            message=f"Selected database to load: {db_widget.selected_connection_name} -"
            f" Schema: {db_widget.selected_schema} - Format: {db_widget.get_db_format}"
        )

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            import_in_qgis(
                gmlas_uri=db_widget.get_database_connection.uri(),
                provider=db_widget.get_db_format,
                schema=db_widget.selected_schema,
            )
        except InputError as e:
            QMessageBox.warning(None, "Error during layer loading", e.args[0])
        except RuntimeError as e:
            QMessageBox.warning(None, "Error during layer loading", e.args[0])
        finally:
            QApplication.restoreOverrideCursor()

    def onWizardLoad(self):
        self.wizard = LoadWizard(self.iface.mainWindow())
        self.wizard.setModal(False)
        self.wizard.show()
        self.wizard.resize(500, 500)
        self.wizard.finished.connect(self.onWizardEnd)

    def onWizardEnd(self, result):
        # destruct the object
        # (this makes sure collapsible states are correctly saved)
        self.wizard.setParent(None)
        self.wizard.deleteLater()

    def onExport(self):
        w = ExportGmlasPanel(self.iface.mainWindow())
        w.exec_()
