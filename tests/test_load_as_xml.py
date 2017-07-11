# -*- coding: utf-8 -*-
# launch it with something like
# QGIS_DEBUG=0 QGIS_PREFIX_PATH=/home/hme/src/QGIS/build/output PYTHONPATH=/home/hme/src/QGIS/build/output/python python3 test_load_as_xml.py

import qgis  # NOQA
from qgis.testing import start_app, unittest

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "gml_application_schema_toolbox"))

from core.load_gml_as_xml import *

start_app()

class TestLoadAsXML(unittest.TestCase):

    def test_1(self):
        f = os.path.join(os.path.dirname(__file__), "..", "samples", "brgm_ef_piezo_50_2.xml")
        l = load_as_xml_layer(f, False, output_local_file = "/tmp/t.gpkg")
        self.assertEqual(l.isValid(), True)
        self.assertEqual(l.featureCount(), 50)

if __name__ == '__main__':
    unittest.main()
