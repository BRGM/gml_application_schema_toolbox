#! python3  # noqa: E265

"""
    Plugin settings.
"""

# standard
import logging

# PyQGIS
from qgis.core import QgsSettings
from qgis.gui import QgsOptionsPageWidget, QgsOptionsWidgetFactory
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QVBoxLayout

# package
from gml_application_schema_toolbox.__about__ import DIR_PLUGIN_ROOT, __title__
from gml_application_schema_toolbox.resources.gui.dlg_settings import SettingsDialog

# ############################################################################
# ########## Globals ###############
# ##################################

logger = logging.getLogger(__name__)

DEFAULT_GMLAS_CONFIG = str(DIR_PLUGIN_ROOT / "conf" / "gmlasconf.xml")

PLG_PREFERENCES: dict = {
    "debug_mode": False,
    "default_access_mode": None,
    "default_db_type": "SQLite",
    "default_gmlas_config": DEFAULT_GMLAS_CONFIG,
    "default_import_method": "gmlas",
    "default_language": "en",
    "default_maxfeatures": 100,
    "default_wfs2_service": None,
    "wfs2_services": [],
}

# ############################################################################
# ########## Classes ###############
# ##################################


class PlgOptionsManager:
    @staticmethod
    def get_plg_settings():
        settings = QgsSettings()
        settings = QgsSettings()
        settings.beginGroup(__title__)

        # options_dict = {
        #     "browser": settings.value(
        #         key="browser", defaultValue=1, type=int
        #     ),  # 1 = QGIS, 2 = system
        # }

        settings.endGroup()

        # return options_dict


class PlgOptionsFactory(QgsOptionsWidgetFactory):
    def __init__(self):
        super().__init__()

    def icon(self):
        return QIcon(str(DIR_PLUGIN_ROOT / "resources/images/mActionAddGMLLayer.svg"))

    def createWidget(self, parent):
        return ConfigOptionsPage(parent)

    def title(self):
        return "GMLAS Toolbox"


class ConfigOptionsPage(QgsOptionsPageWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.dlg_settings = SettingsDialog(self)
        self.dlg_settings.buttonBox.hide()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.dlg_settings.setLayout(layout)
        self.setLayout(layout)
        self.setObjectName("mOptionsPage{}".format(__title__))

    def apply(self):
        """Called to permanently apply the settings shown in the options page (e.g. \
        save them to QgsSettings objects). This is usually called when the options \
        dialog is accepted."""
        self.dlg_settings.save_settings()
