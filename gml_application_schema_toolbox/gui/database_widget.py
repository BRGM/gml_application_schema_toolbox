#! python3  # noqa: E265

# standard library
from pathlib import Path

# PyQGIS
from qgis.core import QgsApplication, QgsProviderRegistry
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QAbstractItemModel, QModelIndex, QSettings, Qt, pyqtSlot
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

# plugin
from gml_application_schema_toolbox.__about__ import DIR_PLUGIN_ROOT, __title__
from gml_application_schema_toolbox.constants import DATABASE_TYPES
from gml_application_schema_toolbox.core.gmlas_postgis_db import GmlasPostgisDB
from gml_application_schema_toolbox.gui import InputError
from gml_application_schema_toolbox.toolbelt import PlgLogger, PlgOptionsManager

# ############################################################################
# ########## Globals ###############
# ##################################

WIDGET, BASE = uic.loadUiType(DIR_PLUGIN_ROOT / "ui/{}.ui".format(Path(__file__).stem))

# ############################################################################
# ########## Classes ###############
# ##################################


# class PgsqlConnectionsModel(QAbstractItemModel):
#     def __init__(self, parent=None):
#         super(PgsqlConnectionsModel, self).__init__(parent)

#         self._settings = QSettings()
#         self._settings.beginGroup("/PostgreSQL/connections/")

#     def _groups(self):
#         return self._settings.childGroups()

#     def parent(self, index):
#         return QModelIndex()

#     def index(self, row, column, parent):
#         return self.createIndex(row, column)

#     def rowCount(self, parent):
#         return len(self._groups())

#     def columnCount(self, parent):
#         return 1

#     def data(self, index, role=Qt.DisplayRole):
#         return self._groups()[index.row()]


class DatabaseWidget(BASE, WIDGET):
    def __init__(self, parent=None, is_input=False):
        super(DatabaseWidget, self).__init__(parent)
        self.log = PlgLogger().log
        self.setupUi(self)

        self._pgsql_db = None

        # icons
        self.btn_refresh_connections.setIcon(
            QgsApplication.getThemeIcon("mActionRefresh.svg")
        )
        self.btn_foreign_keys_add.setIcon(
            QgsApplication.getThemeIcon("/mActionAdd.svg")
        )
        self.btn_foreign_keys_del.setIcon(
            QgsApplication.getThemeIcon("/mActionRemove.svg")
        )

        # connect widgets to methods
        self.cbb_connections.activated.connect(self.switch_form_according_database_type)
        self.btn_refresh_connections.pressed.connect(self.populate_connections_combobox)
        # self.btn_foreign_keys_add.clicked.connect(
        #     self._pgsql_db.add_foreign_key_constraints
        # )
        # self.btn_foreign_keys_del.clicked.connect(
        #     self._pgsql_db.drop_foreign_key_constraints
        # )

        # fill widgets
        self.populate_connections_combobox()
        self.switch_form_according_database_type()

    def populate_connections_combobox(self):
        """List existing database connections into the combobox."""
        # clear and add a placeholder to avoid select item before user does by himself
        self.cbb_connections.clear()
        self.cbb_connections.addItem(" - ", "")

        # list connections per compatible database types (defined in constants)
        for db_type in DATABASE_TYPES:
            connections = (
                QgsProviderRegistry.instance().providerMetadata(db_type).connections()
            )

            if not len(connections):
                continue

            for connection_name in connections:
                self.cbb_connections.addItem(
                    connections.get(connection_name).icon(),
                    connection_name,
                    connections.get(connection_name),
                )
        self.log(
            message="DEBUG - {} connections listed.".format(
                self.cbb_connections.count() - 1
            ),
            log_level=4,
        )
        self.cbb_connections.setEnabled(True)

        # check if at least one database connection exists
        if self.cbb_connections.count() == 1:
            self.log(
                message=self.tr(
                    "No database connection configured. "
                    "Please add one through the QGIS source manager."
                ),
                log_level=1,
                push=True,
            )
            self.cbb_connections.setEnabled(False)

    def switch_form_according_database_type(self):
        """Update the form depending on connection"""
        selected_conn = self.cbb_connections.itemData(
            self.cbb_connections.currentIndex()
        )
        # ignore if it's the placeholder
        if isinstance(selected_conn, str):
            self.pgsqlFormWidget.setEnabled(False)
            return

        if selected_conn.providerKey().startswith("postgr"):
            self.pgsqlFormWidget.setEnabled(True)
            # list schemas
            self.cbb_schemas.clear()
            for schema_name in sorted(selected_conn.schemas()):
                self.cbb_schemas.addItem(schema_name)
        elif selected_conn.providerKey().startswith("spatialite"):
            self.pgsqlFormWidget.setEnabled(False)
        else:
            pass
