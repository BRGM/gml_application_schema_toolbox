# -*- coding: utf-8 -*-

import os

from qgis.core import QgsApplication
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSlot, Qt
from qgis.PyQt.QtWidgets import QFileDialog, QListWidgetItem

from gml_application_schema_toolbox.core.settings import settings
from gml_application_schema_toolbox import name as plugin_name


WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'settings_dialog.ui'))


class SettingsDialog(BASE, WIDGET):

    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)

        self.load_settings()

    def set_icon(self, button, icon):
        button.setIcon(QgsApplication.getThemeIcon(icon))

    def load_settings(self):
        self.featureLimitBox.setValue(int(settings.value('default_maxfeatures')))
        self.set_import_method(settings.value('default_import_method'))
        self.gmlasConfigLineEdit.setText(settings.value('default_gmlas_config'))
        self.languageLineEdit.setText(settings.value('default_language'))
        self.set_db_type(settings.value('default_db_type'))
        self.set_access_mode(settings.value('default_access_mode'))
        self.httpUserAgentEdit.setText(settings.value('http_user_agent', plugin_name()))

    def save_settings(self):
        settings.setValue('default_maxfeatures', self.featureLimitBox.value())
        settings.setValue('default_import_method', self.import_method())
        settings.setValue('default_language', self.languageLineEdit.text())
        settings.setValue('default_db_type', self.db_type())
        settings.setValue('default_access_mode', self.access_mode())
        settings.setValue('http_user_agent', self.http_user_agent())

    def set_import_method(self, value):
        if value == 'gmlas':
            self.gmlasRadioButton.setChecked(True)
        if value == 'xml':
            self.xmlRadioButton.setChecked(True)

    def import_method(self):
        if self.gmlasRadioButton.isChecked():
            return 'gmlas'
        if self.xmlRadioButton.isChecked():
            return 'xml'

    def http_user_agent(self):
        return httpUserAgentEdit.text()

    @pyqtSlot()
    def on_gmlasConfigButton_clicked(self):
        path, filter = QFileDialog.getOpenFileName(self,
            self.tr("Open GMLAS config file"),
            self.gmlasConfigLineEdit.text(),
            self.tr("XML Files (*.xml)"))
        if path:
            self.gmlasConfigLineEdit.setText(path)

    def set_db_type(self, value):
        if value == 'SQLite':
            self.sqliteRadioButton.setChecked(True)
        if value == 'PostgreSQL':
            self.pgsqlRadioButton.setChecked(True)

    def db_type(self):
        if self.sqliteRadioButton.isChecked():
            return 'SQLite'
        if self.pgsqlRadioButton.isChecked():
            return 'PostgreSQL'

    def set_access_mode(self, value):
        if value is None:
            self.createRadioButton.setChecked(True)
        if value == "update":
            self.updateRadioButton.setChecked(True)
        if value == 'append':
            self.appendRadioButton.setChecked(True)
        if value == 'overwrite':
            self.overwriteRadioButton.setChecked(True)

    def access_mode(self):
        if self.createRadioButton.isChecked():
            return None
        if self.updateRadioButton.isChecked():
            return "update"
        if self.appendRadioButton.isChecked():
            return "append"
        if self.overwriteRadioButton.isChecked():
            return "overwrite"

    def accept(self):
        self.save_settings()
        super(SettingsDialog, self).accept()
