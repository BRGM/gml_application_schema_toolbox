# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QSettings

def settings():
    """Global settings of the application"""
    return QSettings("gml_application_schema_toolbox")
