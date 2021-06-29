#! python3  # noqa E265

"""
    Usage from the repo root folder:

    .. code-block:: bash

        # for whole tests
        python -m unittest tests.test_plg_preferences
        # for specific test
        python -m unittest tests.test_plg_preferences.TestPlgPreferences.test_plg_preferences_structure
"""

# standard library
import unittest

# project
from gml_application_schema_toolbox.__about__ import (
    DIR_PLUGIN_ROOT,
    __title__,
    __version__,
)
from gml_application_schema_toolbox.toolbelt.preferences import PlgSettingsStructure

# ############################################################################
# ########## Classes #############
# ################################


class TestPlgPreferences(unittest.TestCase):
    def test_plg_preferences_structure(self):
        """Test version note named tuple structure and mechanisms."""
        settings = PlgSettingsStructure()

        # global
        self.assertTrue(hasattr(settings, "debug_mode"))
        self.assertIsInstance(settings.debug_mode, bool)
        self.assertEqual(settings.debug_mode, False)

        self.assertTrue(hasattr(settings, "version"))
        self.assertIsInstance(settings.version, str)
        self.assertEqual(settings.version, __version__)

        # network
        self.assertTrue(hasattr(settings, "network_http_user_agent"))
        self.assertIsInstance(settings.network_http_user_agent, str)
        self.assertEqual(settings.network_http_user_agent, f"{__title__}/{__version__}")
        self.assertTrue(hasattr(settings, "network_language"))
        self.assertIsInstance(settings.network_language, str)
        self.assertEqual(settings.network_language, "en")
        self.assertTrue(hasattr(settings, "network_max_features"))
        self.assertIsInstance(settings.network_max_features, int)
        self.assertEqual(settings.network_max_features, 100)

        # usage
        self.assertTrue(hasattr(settings, "impex_access_mode"))
        self.assertIsInstance(settings.impex_access_mode, int)
        self.assertEqual(settings.impex_access_mode, 1)
        self.assertTrue(hasattr(settings, "impex_db_type"))
        self.assertIsInstance(settings.impex_db_type, int)
        self.assertEqual(settings.impex_db_type, 1)
        self.assertTrue(hasattr(settings, "impex_import_method"))
        self.assertIsInstance(settings.impex_import_method, int)
        self.assertEqual(settings.impex_import_method, 1)
        self.assertTrue(hasattr(settings, "impex_gmlas_config"))
        self.assertIsInstance(settings.impex_gmlas_config, str)
        self.assertEqual(
            settings.impex_gmlas_config, str(DIR_PLUGIN_ROOT / "conf" / "gmlasconf.xml")
        )

        self.assertTrue(hasattr(settings, "last_file"))
        self.assertIsInstance(settings.last_file, (str, type(None)))
        self.assertIsNone(settings.last_file, None)

        self.assertTrue(hasattr(settings, "last_dowloaded_file"))
        self.assertIsInstance(settings.last_dowloaded_file, (str, type(None)))
        self.assertIsNone(settings.last_dowloaded_file, None)

        self.assertTrue(hasattr(settings, "last_path"))
        self.assertIsInstance(settings.last_path, (str, type(None)))
        self.assertIsNone(settings.last_path, None)

        self.assertTrue(hasattr(settings, "last_downloaded_path"))
        self.assertIsInstance(settings.last_downloaded_path, (str, type(None)))
        self.assertIsNone(settings.last_downloaded_path, None)

        self.assertTrue(hasattr(settings, "last_source"))
        self.assertIsInstance(settings.last_source, str)
        self.assertIsNone(settings.last_source, "file")


# ############################################################################
# ####### Stand-alone run ########
# ################################
if __name__ == "__main__":
    unittest.main()
