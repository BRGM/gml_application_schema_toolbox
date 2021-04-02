#! python3  # noqa: E265

"""
    Plugin settings.
"""

# standard
import logging

# PyQGIS
from qgis.core import QgsSettings

# package
from gml_application_schema_toolbox.__about__ import DIR_PLUGIN_ROOT, __title__
from gml_application_schema_toolbox.resources.gui.dlg_settings import SettingsDialog
from gml_application_schema_toolbox.toolbelt import PlgLogger

# ############################################################################
# ########## Globals ###############
# ##################################

logger = logging.getLogger(__name__)
plg_logger = PlgLogger()

DEFAULT_GMLAS_CONFIG = str(DIR_PLUGIN_ROOT / "conf" / "gmlasconf.xml")

PLG_PREFERENCES: dict = {
    # download
    "default_maxfeatures": 100,
    "default_gmlas_config": DEFAULT_GMLAS_CONFIG,
    "default_wfs2_service": None,
    "wfs2_services": [],
    # import/export
    "impex_access_mode": None,
    "impex_db_type": "SQLite",
    "impex_import_method": "gmlas",
    "impex_language": "en",
    # usage
    # global
    "debug_mode": False,
}

# ############################################################################
# ########## Classes ###############
# ##################################


class PlgOptionsManager:
    @staticmethod
    def get_plg_settings() -> dict:
        """Load and return plugin settings as a dictionary. \
        Useful to get user preferences across plugin logic.

        :return: plugin settings
        :rtype: dict
        """
        settings = QgsSettings()
        settings.beginGroup(__title__)

        options_dict = {
            "impex_access_mode": settings.value(
                key="impex_access_mode", defaultValue=1, type=int
            ),
            "impex_db_type": settings.value(
                key="impex_db_type", defaultValue=1, type=int
            ),
            "impex_import_method": settings.value(
                key="impex_import_method", defaultValue=1, type=int
            ),
        }

        settings.endGroup()

        return options_dict

    @staticmethod
    def get_value_from_key(key: str, default=None, exp_type=None):
        """Load and return plugin settings as a dictionary. \
        Useful to get user preferences across plugin logic.

        :return: plugin settings value matching key
        """
        if key not in PLG_PREFERENCES:
            logger.error(
                "Bad settings key. Must be one of: {}".format(
                    ",".join(PLG_PREFERENCES.keys())
                )
            )
            return None

        settings = QgsSettings()
        settings.beginGroup(__title__)

        try:
            out_value = settings.value(key=key, defaultValue=default, type=exp_type)
        except Exception as err:
            logger.error(err)
            plg_logger.log(err)
            out_value = None

        settings.endGroup()

        return out_value
