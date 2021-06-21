#! python3  # noqa E265

"""
    Usage from the repo root folder:

    Launch it with something like

    `QGIS_DEBUG=0 QGIS_PREFIX_PATH=/home/hme/src/QGIS/build/output PYTHONPATH=/home/hme/src/QGIS/build/output/python python3 test_custom_viewers.py`

    .. code-block:: bash

        # for whole tests
        python -m unittest tests.test_custom_viewers
        # for specific test
        python -m unittest tests.test_custom_viewers.TestCustomViewers.test_custom_viewers_layer
"""


# PyQGIS
from qgis.testing import unittest
from sip import wrappertype

# project
from gml_application_schema_toolbox.gui.custom_viewers import get_custom_viewers


# ############################################################################
# ########## Classes #############
# ################################
class TestCustomViewers(unittest.TestCase):
    """Tests"""

    def test_custom_viewers_loader(self):
        for viewer_cls, _ in get_custom_viewers().values():
            self.assertIsInstance(viewer_cls, wrappertype)
            self.assertIsNone(_)


# ############################################################################
# ####### Stand-alone run ########
# ################################
if __name__ == "__main__":
    unittest.main()
