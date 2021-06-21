#! python3  # noqa E265

"""
    Usage from the repo root folder:

    .. code-block:: bash
        # for whole tests
        python -m unittest tests.test_plg_metadata
        # for specific test
        python -m unittest tests.test_plg_metadata.TestPluginMetadata.test_version_semver
"""

# standard library
import unittest

# 3rd party
from semver import VersionInfo

# project
from gml_application_schema_toolbox import __about__

# ############################################################################
# ########## Classes #############
# ################################


class TestPluginMetadata(unittest.TestCase):
    def test_version_semver(self):
        """Test if version comply with semantic versioning."""
        self.assertTrue(VersionInfo.isvalid(__about__.__version__))


# ############################################################################
# ####### Stand-alone run ########
# ################################
if __name__ == "__main__":
    unittest.main()
