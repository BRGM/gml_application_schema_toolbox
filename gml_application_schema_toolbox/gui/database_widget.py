#! python3  # noqa: E265

# standard library
from pathlib import Path
from typing import Union

# PyQGIS
from qgis.core import (
    QgsAbstractDatabaseProviderConnection,
    QgsApplication,
    QgsProviderRegistry,
)
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QWidget

# plugin
from gml_application_schema_toolbox.__about__ import DIR_PLUGIN_ROOT
from gml_application_schema_toolbox.constants import DATABASE_TYPES
from gml_application_schema_toolbox.toolbelt import PlgLogger

# ############################################################################
# ########## Globals ###############
# ##################################

WIDGET, BASE = uic.loadUiType(DIR_PLUGIN_ROOT / "ui/{}.ui".format(Path(__file__).stem))

# ############################################################################
# ########## Classes ###############
# ##################################


class DatabaseWidget(BASE, WIDGET):
    """Form allowing the end-user picks the database connection to use.

    :param BASE: [description]
    :type BASE: [type]
    :param WIDGET: [description]
    :type WIDGET: [type]
    """

    def __init__(self, parent: QWidget = None, is_input: bool = False):
        """Form initialization.

        :param parent: [description], defaults to None
        :type parent: QWidget, optional
        :param is_input: [description], defaults to False
        :type is_input: bool, optional
        """
        super(DatabaseWidget, self).__init__(parent)
        self.log = PlgLogger().log
        self.setupUi(self)

        self._pgsql_db = None

        self.placeholder = " - "

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
        self.cbb_connections.addItem(self.placeholder, "")

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
        """Update the form depending on selected connection."""
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

    @property
    def get_database_connection(
        self,
    ) -> Union[QgsAbstractDatabaseProviderConnection, None]:
        """Retrieve selected connection.

        :return: selected connection or None
        :rtype: Union[QgsAbstractDatabaseProviderConnection, None]
        """
        selected_conn = self.cbb_connections.itemData(
            self.cbb_connections.currentIndex()
        )

        # ignore if it's the placeholder
        if isinstance(selected_conn, str):
            return None

        # determmine database type
        return selected_conn

    @property
    def get_db_format(self) -> Union[str, None]:
        """Database format as lowercased string.

        :return: database provider key
        :rtype: Union[str, None]
        """
        return self.get_database_connection.providerKey() or None

    @property
    def selected_connection_name(self) -> Union[str, None]:
        """Return selected connection name.

        :return: connection name
        :rtype: Union[str, None]
        """
        if self.cbb_connections.currentText() == self.placeholder:
            return None

        return self.cbb_connections.currentText() or None

    @property
    def selected_schema(self) -> Union[str, None]:
        """Return selected schema.

        :return: schema name
        :rtype: Union[str, None]
        """
        if self.get_db_format == "postgres":
            return self.cbb_schemas.currentText() or None
        else:
            return None
