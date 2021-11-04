#! python3  # noqa: E265

# standard library
from pathlib import Path
from typing import List, Union

# PyQGIS
from qgis.core import (
    QgsAbstractDatabaseProviderConnection,
    QgsApplication,
    QgsDataSourceUri,
    QgsProviderConnectionException,
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


class ForeignKey:
    """Foreign key class."""

    def __init__(
        self, table: str, column: str, referenced_table: str, referenced_column: str
    ):
        """Foreign key initialization

        :param table: table name
        :type table: str
        :param column: column name
        :type column: str
        :param referenced_table: referenced table name
        :type referenced_table: str
        :param referenced_column: referenced column name
        :type referenced_column: str
        """
        self.table = table
        self.column = column
        self.referenced_table = referenced_table
        self.referenced_column = referenced_column
        self.name = "{self.column}_fkey".format(self=self)

    def __str__(self):
        return (
            'ForeignKey("{self.name}", '
            '"{self.table}"."{self.column}" => '
            '"{self.referenced_table}"."{self.referenced_column}")'.format(self=self)
        )


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
        self.btn_foreign_keys_add.clicked.connect(self.btn_add_foreign_key_constraints)
        self.btn_foreign_keys_del.clicked.connect(self.btn_drop_foreign_key_constraints)

        # fill widgets
        self.populate_connections_combobox()
        self.switch_form_according_database_type()

    def btn_add_foreign_key_constraints(self):
        """Add constraints to the selected schema."""
        try:
            for foreign_key in self.get_foreign_keys:
                self.log(message=f"{foreign_key}", log_level=4)
                self._add_unique_constraint(
                    self.selected_schema,
                    foreign_key.referenced_table,
                    foreign_key.referenced_column,
                )
                self._add_foreign_key_constraint(self.selected_schema, foreign_key)
        except Exception as err:
            self.log(message=err, log_level=2, push=True)
            raise

    def btn_drop_foreign_key_constraints(self):
        """Delete constraints in the selected schema."""
        try:
            for foreign_key in self.get_foreign_keys:
                self._drop_constraint(
                    self.selected_schema,
                    table=foreign_key.table,
                    constraint=foreign_key.name,
                )
                self._drop_constraint(
                    self.selected_schema,
                    table=foreign_key.referenced_table,
                    constraint=(
                        "{table}_{column}_unique".format(
                            table=foreign_key.referenced_table,
                            column=foreign_key.referenced_column,
                        )
                    ),
                )
        except Exception as err:
            self.log(message=err, log_level=2, push=True)
            raise

    def _add_foreign_key_constraint(self, schema: str, foreign_key: ForeignKey):
        """Add a foreign key constraint to a table.

        :param schema: schema name
        :type schema: str
        :param foreign_key: foreign key
        :type foreign_key: ForeignKey
        """
        if self._constraint_exists(
            schema=schema, table=foreign_key.table, constraint=foreign_key.name
        ):
            return

        conn = self.get_database_connection
        with open(DIR_PLUGIN_ROOT / "sql/add_foreign_key_constraint.sql", "r") as f:
            sql = f.read().format(schema=schema, foreign_key=foreign_key)

        self.log(
            message=f"DEBUG Add foreign key constraint to {foreign_key.table}",
            log_level=4,
        )
        self.log(message=f"{sql}", log_level=4)
        try:
            conn.executeSql(sql)
        except QgsProviderConnectionException as err:
            self.log(message=err, log_level=2, push=True)

    def _add_unique_constraint(self, schema: str, table: str, column: str):
        """Add a unique constraint to a table.

        :param schema: schema name
        :type schema: str
        :param table: table name
        :type table: str
        :param column: column name
        :type column: str
        """
        constraint = "{table}_{column}_unique".format(table=table, column=column)

        if self._constraint_exists(schema=schema, table=table, constraint=constraint):
            return

        conn = self.get_database_connection
        with open(DIR_PLUGIN_ROOT / "sql/add_unique_constraint.sql", "r") as f:
            sql = f.read().format(
                schema=schema, table=table, constraint=constraint, column=column
            )

        self.log(
            message=f"DEBUG Add unique constraint to {table} ({column})",
            log_level=4,
        )
        self.log(message=f"{sql}", log_level=4)
        try:
            conn.executeSql(sql)
        except QgsProviderConnectionException as err:
            self.log(message=err, log_level=2, push=True)

    def _constraint_exists(self, schema: str, table: str, constraint: str) -> bool:
        """Check if constraint already exists in a table.

        :param schema: [description]
        :type schema: str
        :param table: [description]
        :type table: str
        :param constraint: [description]
        :type constraint: str
        :return: [description]
        :rtype: bool
        """
        conn = self.get_database_connection

        with open(DIR_PLUGIN_ROOT / "sql/constraint_exists.sql", "r") as f:
            sql = f.read().format(schema=schema, table=table, constraint=constraint)

        self.log(
            message=f"DEBUG Check if constraint already exists in {table} ({constraint})",
            log_level=4,
        )
        self.log(message=f"{sql}", log_level=4)
        try:
            result = conn.executeSql(sql)
        except QgsProviderConnectionException as err:
            self.log(message=err, log_level=2, push=True)
        self.log(message=f"DEBUG {result}", log_level=4)
        return result[0][0] == 1

    def _drop_constraint(self, schema: str, table: str, constraint: str):
        """Drop constraint in a table.

        :param schema: schema name
        :type schema: str
        :param table: table name
        :type table: str
        :param constraint: constraint name
        :type constraint: str
        """
        if not self._constraint_exists(schema, table, constraint):
            return

        conn = self.get_database_connection
        with open(DIR_PLUGIN_ROOT / "sql/drop_constraint.sql", "r") as f:
            sql = f.read().format(schema=schema, table=table, constraint=constraint)

        self.log(
            message=f"DEBUG Drop constraint in {table} ({constraint})",
            log_level=4,
        )
        self.log(message=f"{sql}", log_level=4)
        try:
            conn.executeSql(sql)
        except QgsProviderConnectionException as err:
            self.log(message=err, log_level=2, push=True)

    def populate_connections_combobox(self):
        """List existing database connections into the combobox."""
        # clear and add a placeholder to avoid select item before user does by himself
        self.cbb_connections.clear()
        self.cbb_connections.addItem(self.placeholder, "")

        # list connections per compatible database types (defined in constants)
        for db_type in DATABASE_TYPES:
            connections = (
                QgsProviderRegistry.instance()
                .providerMetadata(db_type)
                .connections(cached=False)
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

        :return: database provider key (postgresql or spatialite)
        :rtype: Union[str, None]
        """
        return self.get_database_connection.providerKey().lower() or None

    @property
    def get_db_name_or_path(self) -> Union[str, None]:
        """Database name or path

        :return: database name
        :rtype: Union[str, None]
        """
        return QgsDataSourceUri(self.get_database_connection.uri()).database() or None

    @property
    def get_foreign_keys(self) -> List[str]:
        """Return list of foreign keys

        :return: foreign keys
        :rtype: List[str]
        """
        foreign_keys = []
        self.log(
            message=f"DEBUG Get foreign keys from {self.get_db_name_or_path} \
            ({self.get_db_format})",
            log_level=4,
        )
        conn = self.get_database_connection
        # one to many
        with open(DIR_PLUGIN_ROOT / "sql/foreign_key_one_to_many.sql", "r") as f:
            sql = f.read().format(schema=self.selected_schema)

        self.log(message=f"{sql}", log_level=4)
        try:
            results = conn.executeSql(sql)
        except QgsProviderConnectionException as err:
            self.log(message=err, log_level=2, push=True)
        for (layer_name, field_name, child_layer, child_pkid) in results:
            foreign_keys.append(
                ForeignKey(
                    table=layer_name,
                    column=field_name,
                    referenced_table=child_layer,
                    referenced_column=child_pkid,
                )
            )

        # many to many
        with open(DIR_PLUGIN_ROOT / "sql/foreign_key_many_to_many.sql", "r") as f:
            sql = f.read().format(schema=self.selected_schema)

        self.log(message=f"DEBUG {sql}", log_level=4)
        try:
            results = conn.executeSql(sql)
        except QgsProviderConnectionException as err:
            self.log(message=err, log_level=2, push=True)
        for (
            field_junction_layer,
            parent_layer,
            parent_pkid,
            child_layer,
            child_pkid,
        ) in results:
            foreign_keys.append(
                ForeignKey(
                    table=field_junction_layer,
                    column="parent_pkid",
                    referenced_table=parent_layer,
                    referenced_column=parent_pkid,
                )
            )
            foreign_keys.append(
                ForeignKey(
                    table=field_junction_layer,
                    column="child_pkid",
                    referenced_table=child_layer,
                    referenced_column=child_pkid,
                )
            )
        return foreign_keys

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

    def schema_create(self, schema_name: str = None) -> str:
        """Create schema into selected database.

        :return: schema name.
        :rtype: str
        """
        if not schema_name or schema_name == self.selected_schema:
            return self.selected_schema

        try:
            self.get_database_connection.createSchema(schema_name)
        except QgsProviderConnectionException:
            pass

        return schema_name
