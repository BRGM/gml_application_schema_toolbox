#! python3  # noqa: E265

"""
    Plugin settings.
"""

# standard
from typing import NamedTuple

# PyQGIS
from qgis.core import QgsSettings

import gml_application_schema_toolbox.toolbelt.log_handler as log_hdlr

# package
from gml_application_schema_toolbox.__about__ import (
    DIR_PLUGIN_ROOT,
    __title__,
    __version__,
)

# ############################################################################
# ########## Classes ###############
# ##################################


class PlgSettingsStructure(NamedTuple):
    """Plugin settings structure and defaults values.

    :param NamedTuple: [description]
    :type NamedTuple: [type]
    """

    # global
    debug_mode: bool = False
    version: str = __version__

    # usage
    impex_access_mode: int = 1
    impex_db_type: int = 1
    impex_import_method: int = 1
    impex_gmlas_config: str = str(DIR_PLUGIN_ROOT / "conf" / "gmlasconf.xml")
    last_file: str = None
    last_downloaded_file: str = None
    last_path: str = None
    last_downloaded_path: str = None
    last_source: str = "file"

    # network
    network_http_user_agent: str = f"{__title__}/{__version__}"
    network_language: str = "en"
    network_max_features: int = 100

    defaults = [
        False,
        __version__,
        None,
        "sqlite",
        str(DIR_PLUGIN_ROOT / "conf" / "gmlasconf.xml"),
        None,
        None,
        None,
        None,
        "en",
        100,
    ]

    @property
    def access_mode_as_str(self) -> str:
        if self.impex_access_mode == 1:
            return "create"
        elif self.impex_access_mode == 2:
            return "update"
        elif self.impex_access_mode == 3:
            return "append"
        elif self.impex_access_mode == 4:
            return "overwrite"
        else:
            log_hdlr.PlgLogger.log(
                f"Invalid access_mode code: {self.impex_access_mode}", log_level=1
            )
            return "create"

    @property
    def db_type_as_str(self) -> str:
        if self.impex_db_type == 1:
            return "postgresql"
        elif self.impex_db_type == 2:
            return "sqlite"
        else:
            log_hdlr.PlgLogger.log(
                f"Invalid db_type code: {self.impex_db_type}", log_level=1
            )
            return "create"

    @property
    def import_method_as_str(self) -> str:
        if self.impex_import_method == 1:
            return "gmlas"
        elif self.impex_import_method == 2:
            return "xml"
        else:
            log_hdlr.PlgLogger.log(
                f"Invalid import_method code: {self.impex_import_method}", log_level=1
            )
            return "create"


class PlgOptionsManager:
    @staticmethod
    def get_plg_settings() -> PlgSettingsStructure:
        """Load and return plugin settings as a dictionary. \
        Useful to get user preferences across plugin logic.

        :return: plugin settings
        :rtype: dict
        """
        settings = QgsSettings()
        settings.beginGroup(__title__)

        options = PlgSettingsStructure(
            # normal
            debug_mode=settings.value(key="debug_mode", defaultValue=False, type=bool),
            version=settings.value(key="version", defaultValue=__version__, type=str),
            # usage
            impex_access_mode=settings.value(
                key="impex_access_mode", defaultValue=1, type=int
            ),
            impex_db_type=settings.value(key="impex_db_type", defaultValue=1, type=int),
            impex_import_method=settings.value(
                key="impex_import_method", defaultValue=1, type=int
            ),
            impex_gmlas_config=settings.value(
                key="impex_gmlas_config",
                defaultValue=str(DIR_PLUGIN_ROOT / "conf" / "gmlasconf.xml"),
                type=str,
            ),
            last_file=settings.value(
                key="last_file",
                defaultValue=None,
                type=str,
            ),
            last_downloaded_file=settings.value(
                key="last_downloaded_file",
                defaultValue=None,
                type=str,
            ),
            last_path=settings.value(
                key="last_path",
                defaultValue=None,
                type=str,
            ),
            last_downloaded_path=settings.value(
                key="last_downloaded_path",
                defaultValue=None,
                type=str,
            ),
            last_source=settings.value(
                key="last_source",
                defaultValue="file",
                type=str,
            ),
            # network
            network_http_user_agent=settings.value(
                key="network_http_user_agent",
                defaultValue=f"{__title__}/{__version__}",
                type=str,
            ),
            network_language=settings.value(
                key="network_language", defaultValue="en", type=str
            ),
            network_max_features=settings.value(
                key="network_max_features", defaultValue=100, type=int
            ),
        )

        settings.endGroup()

        # log_hdlr.PlgLogger.log("Settings retrieved", log_level=4)
        return options

    @staticmethod
    def get_value_from_key(key: str, default=None, exp_type=None):
        """Load and return plugin settings as a dictionary. \
        Useful to get user preferences across plugin logic.

        :return: plugin settings value matching key
        """
        if not hasattr(PlgSettingsStructure, key):
            log_hdlr.PlgLogger.log(
                message="Bad settings key: {}. Must be one of: {}".format(
                    key, ",".join(PlgSettingsStructure._fields)
                ),
                log_level=1,
            )
            return None

        settings = QgsSettings()
        settings.beginGroup(__title__)

        try:
            out_value = settings.value(key=key, defaultValue=default, type=exp_type)
        except Exception as err:
            log_hdlr.PlgLogger.log(
                message="Error occurred trying to get settings: {}.Trace: {}".format(
                    key, err
                )
            )
            out_value = None

        settings.endGroup()

        return out_value

    @classmethod
    def set_value_from_key(cls, key: str, value):
        """Load and return plugin settings as a dictionary. \
        Useful to get user preferences across plugin logic.

        :return: plugin settings value matching key
        """
        if not hasattr(PlgSettingsStructure, key):
            log_hdlr.PlgLogger.log(
                message="Bad settings key: {}. Must be one of: {}".format(
                    key, ",".join(PlgSettingsStructure._fields)
                ),
                log_level=2,
            )
            return False

        settings = QgsSettings()
        settings.beginGroup(__title__)

        try:
            settings.setValue(key, value)
            out_value = True
            log_hdlr.PlgLogger.log(
                f"Setting `{key}` saved with value `{value}`", log_level=4
            )
        except Exception as err:
            log_hdlr.PlgLogger.log(
                message="Error occurred trying to set settings: {}.Trace: {}".format(
                    key, err
                )
            )
            out_value = False

        settings.endGroup()

        return out_value

    @classmethod
    def save_from_object(cls, plugin_settings_obj: PlgSettingsStructure):
        """Load and return plugin settings as a dictionary. \
        Useful to get user preferences across plugin logic.

        :return: plugin settings value matching key
        """
        settings = QgsSettings()
        settings.beginGroup(__title__)

        for k, v in plugin_settings_obj._asdict().items():
            cls.set_value_from_key(k, v)

        settings.endGroup()
