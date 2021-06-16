#! python3  # noqa E265

"""
    Usage from the repo root folder:

    Launch it with something like

    `QGIS_DEBUG=0 QGIS_PREFIX_PATH=/home/hme/src/QGIS/build/output PYTHONPATH=/home/hme/src/QGIS/build/output/python python3 test_load_as_xml.py`

    .. code-block:: bash

        # for whole tests
        python -m unittest tests.test_load_as_xml
        # for specific test
        python -m unittest tests.test_load_as_xml.TestLoadAsXML.test_load_as_xml_layer
"""


# standard library
from pathlib import Path

# PyQGIS
import qgis  # NOQA
from qgis.testing import start_app, unittest

# project
from gml_application_schema_toolbox.core.load_gml_as_xml import load_as_xml_layer

start_app()


class TestLoadAsXML(unittest.TestCase):
    def test_load_as_xml_layer(self):
        sample_file = Path("tests/samples/brgm_ef_piezo_50_2.xml")
        layer_gmloaded = load_as_xml_layer(
            str(sample_file.resolve()), False, output_local_file="/tmp/t.gpkg"
        )
        self.assertEqual(layer_gmloaded.isValid(), True)
        self.assertEqual(layer_gmloaded.featureCount(), 50)


if __name__ == "__main__":
    unittest.main()
