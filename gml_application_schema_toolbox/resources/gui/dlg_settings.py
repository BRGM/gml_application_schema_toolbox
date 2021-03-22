#! python3  # noqa: E265

"""
    Plugin settings dialog.
"""

# standard
import logging
from pathlib import Path

# PyQGIS
from qgis.core import QgsSettings
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QFileDialog, QWidget

# project
from gml_application_schema_toolbox.__about__ import __title__
from gml_application_schema_toolbox.core.settings import settings
from gml_application_schema_toolbox.toolbelt import PlgLogger

# ############################################################################
# ########## Globals ###############
# ##################################

logger = logging.getLogger(__name__)
FORM_CLASS, _ = uic.loadUiType(
    Path(__file__).parent / "{}.ui".format(Path(__file__).stem)
)


# ############################################################################
# ########## Classes ###############
# ##################################


class SettingsDialog(QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)
        self.log = PlgLogger().log

        # load previously saved settings
        self.load_settings()

    def closeEvent(self, event):
        """Map on plugin close.

        :param event: [description]
        :type event: [type]
        """
        self.closingPlugin.emit()
        event.accept()

    def load_settings(self):
        """Load options from QgsSettings into UI form."""
        # open settings group
        settings = QgsSettings()
        settings.beginGroup(__title__)

        # retrieve options
        self.featureLimitBox.setValue(int(settings.value("default_maxfeatures")))
        self.set_import_method(settings.value("default_import_method"))
        self.gmlasConfigLineEdit.setText(settings.value("default_gmlas_config"))
        self.languageLineEdit.setText(settings.value("default_language"))
        self.set_db_type(settings.value("default_db_type"))
        self.set_access_mode(settings.value("default_access_mode"))
        self.httpUserAgentEdit.setText(settings.value("http_user_agent", __title__))

        # end
        settings.endGroup()

    def save_settings(self):
        """Save options from UI form into QSettings."""
        settings.setValue("default_maxfeatures", self.featureLimitBox.value())
        settings.setValue("default_import_method", self.import_method())
        settings.setValue("default_language", self.languageLineEdit.text())
        settings.setValue("default_db_type", self.db_type())
        settings.setValue("default_access_mode", self.access_mode())
        settings.setValue("http_user_agent", self.http_user_agent())

    def set_import_method(self, value):
        if value == "gmlas":
            self.gmlasRadioButton.setChecked(True)
        if value == "xml":
            self.xmlRadioButton.setChecked(True)

    def import_method(self):
        if self.gmlasRadioButton.isChecked():
            return "gmlas"
        if self.xmlRadioButton.isChecked():
            return "xml"

    def http_user_agent(self):
        return self.httpUserAgentEdit.text()

    @pyqtSlot()
    def on_gmlasConfigButton_clicked(self):
        path, suffix_filter = QFileDialog.getOpenFileName(
            self,
            self.tr("Open GMLAS config file"),
            self.gmlasConfigLineEdit.text(),
            self.tr("XML Files (*.xml)"),
        )
        if path:
            self.gmlasConfigLineEdit.setText(path)

    def set_db_type(self, value):
        if value == "SQLite":
            self.sqliteRadioButton.setChecked(True)
        if value == "PostgreSQL":
            self.pgsqlRadioButton.setChecked(True)

    def db_type(self):
        if self.sqliteRadioButton.isChecked():
            return "SQLite"
        if self.pgsqlRadioButton.isChecked():
            return "PostgreSQL"

    def set_access_mode(self, value):
        if value is None:
            self.createRadioButton.setChecked(True)
        if value == "update":
            self.updateRadioButton.setChecked(True)
        if value == "append":
            self.appendRadioButton.setChecked(True)
        if value == "overwrite":
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

    def reject(self):
        super(SettingsDialog, self).reject()
