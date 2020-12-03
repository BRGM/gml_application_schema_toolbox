import os

from qgis.PyQt.QtCore import QSettings

from gml_application_schema_toolbox import name as plugin_name

DEFAULT_GMLAS_CONFIG = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "conf", "gmlasconf.xml")
)

defaults = {
    "default_maxfeatures": 100,
    "wfs2_services": [],
    "default_wfs2_service": None,
    "default_import_method": "gmlas",
    "default_gmlas_config": DEFAULT_GMLAS_CONFIG,
    "default_language": "en",
    "default_db_type": "SQLite",
    "default_access_mode": None,
}

settings = QSettings()
settings.beginGroup(plugin_name())
for key, value in defaults.items():
    if not settings.contains(key):
        settings.setValue(key, value)
