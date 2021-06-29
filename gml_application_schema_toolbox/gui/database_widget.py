#! python3  # noqa: E265

import os
from pathlib import Path

from qgis.core import QgsApplication
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QAbstractItemModel, QModelIndex, QSettings, Qt, pyqtSlot
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

from gml_application_schema_toolbox.__about__ import __title__
from gml_application_schema_toolbox.core.gmlas_postgis_db import GmlasPostgisDB
from gml_application_schema_toolbox.gui import InputError
from gml_application_schema_toolbox.toolbelt import PlgOptionsManager

WIDGET, BASE = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "..", "ui", "database_widget.ui")
)


class PgsqlConnectionsModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super(PgsqlConnectionsModel, self).__init__(parent)

        self._settings = QSettings()
        self._settings.beginGroup("/PostgreSQL/connections/")

    def _groups(self):
        return self._settings.childGroups()

    def parent(self, index):
        return QModelIndex()

    def index(self, row, column, parent):
        return self.createIndex(row, column)

    def rowCount(self, parent):
        return len(self._groups())

    def columnCount(self, parent):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        return self._groups()[index.row()]


class DatabaseWidget(BASE, WIDGET):
    def __init__(self, parent=None, is_input=False):
        super(DatabaseWidget, self).__init__(parent)
        self.setupUi(self)
        plg_settings = PlgOptionsManager().get_plg_settings()
        self.set_accept_mode(QFileDialog.AcceptOpen)

        self._pgsql_db = None
        self._is_input = is_input
        if not is_input:
            self.sqlitePathLineEdit.setPlaceholderText("Create a temporary file")

        self.pgsqlFormWidget.setVisible(False)
        self.pgsqlConnectionsBox.setModel(PgsqlConnectionsModel())
        self.pgsqlConnectionsRefreshButton.setIcon(
            QgsApplication.getThemeIcon("/mActionRefresh.svg")
        )
        self.addFkeysButton.setIcon(QgsApplication.getThemeIcon("/mActionAdd.svg"))
        self.dropFkeysButton.setIcon(QgsApplication.getThemeIcon("/mActionRemove.svg"))

        self.set_format(plg_settings.db_type_as_str)

    def set_accept_mode(self, accept_mode):
        """QFileDialog.AcceptOpen or QFileDialog.AcceptSave"""
        self._accept_mode = accept_mode
        self.pgsqlSchemaBox.setEditable(accept_mode == QFileDialog.AcceptSave)

    @pyqtSlot(bool)
    def on_sqliteRadioButton_toggled(self, checked):
        self.sqliteFormWidget.setVisible(self.sqliteRadioButton.isChecked())

    @pyqtSlot(bool)
    def on_pgsqlRadioButton_toggled(self, checked):
        self.pgsqlFormWidget.setVisible(self.pgsqlRadioButton.isChecked())

    @pyqtSlot()
    def on_sqlitePathButton_clicked(self):
        current_path = self.sqlitePathLineEdit.text()

        if self._accept_mode == QFileDialog.AcceptOpen:
            filepath, suffix_filter = QFileDialog.getOpenFileName(
                parent=self,
                caption=self.tr("Open SQLite database"),
                directory=current_path,
                filter=self.tr("SQLite Files (*.sqlite)"),
            )
        else:
            filepath, suffix_filter = QFileDialog.getSaveFileName(
                parent=self,
                caption=self.tr("Save to SQLite database"),
                directory=current_path,
                filter=self.tr("SQLite Files (*.sqlite)"),
            )
            if filepath:
                filepath = Path(filepath)
                if filepath.suffix != ".sqlite":
                    filepath = Path(str(filepath) + ".sqlite")
                self.sqlitePathLineEdit.setText(str(filepath.resolve()))

    @pyqtSlot(str)
    def on_pgsqlConnectionsBox_currentIndexChanged(self, text):
        if self.pgsqlConnectionsBox.currentIndex() == -1:
            self._pgsql_db = None
        else:
            self._pgsql_db = GmlasPostgisDB.from_name(
                self.pgsqlConnectionsBox.currentText()
            )

        self.pgsqlSchemaBox.clear()
        if self._pgsql_db is None:
            return
        schemas = sorted([schema[1] for schema in self._pgsql_db.list_schemas()])
        for schema in schemas:
            self.pgsqlSchemaBox.addItem(schema)

    @pyqtSlot()
    def on_pgsqlConnectionsRefreshButton_clicked(self):
        self.pgsqlConnectionsBox.setModel(PgsqlConnectionsModel())

    @pyqtSlot()
    def on_addFkeysButton_clicked(self):
        self._pgsql_db.add_foreign_key_constraints(self.schema())

    @pyqtSlot()
    def on_dropFkeysButton_clicked(self):
        self._pgsql_db.drop_foreign_key_constraints(self.schema())

    def set_format(self, value):
        if value == "sqlite":
            self.sqliteRadioButton.setChecked(True)
        if value == "postgresql":
            self.pgsqlRadioButton.setChecked(True)

    def get_db_format(self):
        if self.sqliteRadioButton.isChecked():
            return "sqlite"
        if self.pgsqlRadioButton.isChecked():
            return "postgresql"

    def datasource_name(self):
        if self.sqliteRadioButton.isChecked():
            path = self.sqlitePathLineEdit.text()
            if path == "" and self._is_input:
                raise InputError("You must select a SQLite file")

            return path
        if self.pgsqlRadioButton.isChecked():
            if self._pgsql_db is None:
                raise InputError("You must select a PostgreSQL connection")
            return "PG:{}".format(self._pgsql_db.uri.connectionInfo(True))

    def schema(self, create=False):
        schema = self.pgsqlSchemaBox.currentText()
        if not create:
            return schema
        # if self.pgsqlSchemaBox.currentIndex() == -1:
        schemas = [schema[1] for schema in self._pgsql_db.list_schemas()]
        if schema not in schemas:
            res = QMessageBox.question(
                self, __title__, self.tr('Create schema "{}" ?').format(schema)
            )
            if res != QMessageBox.Yes:
                raise InputError()
            self._pgsql_db.create_schema(schema)
        return schema
