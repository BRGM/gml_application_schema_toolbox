# -*- coding: utf-8 -*-
# launch it with something like
# QGIS_DEBUG=0 QGIS_PREFIX_PATH=/home/hme/src/QGIS/build/output PYTHONPATH=/home/hme/src/QGIS/build/output/python python3 test_load_in_qgis.py

import qgis
from qgis.testing import start_app, unittest

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "gml_application_schema_toolbox"))

from core.load_gmlas_in_qgis import *

start_app()

class TestLoadInQGIS(unittest.TestCase):

    def test_1(self):
        f = os.path.join(os.path.dirname(__file__), "..", "samples", "gmlas.sqlite")
        import_in_qgis("dbname='{}'".format(f), "spatialite")
        QgsProject.instance().write("test.qgs")

if __name__ == '__main__':
    unittest.main()
