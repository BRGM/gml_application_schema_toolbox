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
from qgis.core import QgsVectorLayer
from qgis.testing import start_app, unittest

# project
from gml_application_schema_toolbox.core.load_gml_as_xml import load_as_xml_layer

# start_app()


# ############################################################################
# ########## Classes #############
# ################################
class TestLoadAsXML(unittest.TestCase):
    def test_load_as_xml_layer(self):
        sample_file = Path("tests/samples/brgm_ef_piezo_50_2.xml")

        self.assertTrue(sample_file.is_file())

        layer_gmloaded = load_as_xml_layer(
            xml_uri=str(sample_file.resolve()),
            is_remote=False,
            output_local_file="/tmp/gmlas_test_load_gml.gpkg",
        )

        self.assertIsInstance(layer_gmloaded, dict)
        self.assertEqual(len(layer_gmloaded), 2)

        for layer in layer_gmloaded.values():
            self.assertIsInstance(layer, QgsVectorLayer)
            self.assertEqual(layer.isValid(), True)
            self.assertEqual(layer.featureCount(), 50)


# ############################################################################
# ####### Stand-alone run ########
# ################################
if __name__ == "__main__":
    unittest.main()
