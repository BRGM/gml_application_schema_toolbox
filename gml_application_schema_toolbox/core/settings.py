#! python3  # noqa: E265

# ############################################################################
# ########## Imports ###############
# ##################################

# Standard library
import os

# PyQGIS
from qgis.core import QgsSettings

# Project
from gml_application_schema_toolbox.__about__ import __title__

# ############################################################################
# ########## Globals ###############
# ##################################

DEFAULT_GMLAS_CONFIG = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "conf", "gmlasconf.xml")
)

defaults = {
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

settings = QgsSettings()
settings.beginGroup(__title__)
for key, value in defaults.items():
    if not settings.contains(key):
        settings.setValue(key, value)
