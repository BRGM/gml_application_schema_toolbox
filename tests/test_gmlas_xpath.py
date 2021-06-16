#! python3  # noqa E265

"""
    Usage from the repo root folder:

    .. code-block:: bash

        # for whole tests
        python -m unittest tests.test_gmlas_xpath
        # for specific test
        python -m unittest tests.test_gmlas_xpath.TestGMLASXPath.test_geologylog
"""

# standard library
import unittest

from gml_application_schema_toolbox.core.gmlas_xpath import GmlAsXPathResolver


class TestGMLASXPath(unittest.TestCase):
    def test_geologylog(self):
        resolver = GmlAsXPathResolver("geology_log1.sqlite", "SQLite", "")
        v = resolver.resolve_xpath(
            "gw_geologylogcoverage",
            "id",
            "ab.ww.402557.log.1.coverage",
            "element/LogValue/value/DataRecord/field/Category/value/text()",
        )
        self.assertEqual(sorted(v), ["Clay", "Gravel", "Soil", "Till"])
        v = resolver.resolve_xpath(
            "gw_geologylogcoverage",
            "id",
            "ab.ww.402557.log.1.coverage",
            "element/LogValue/fromDepth/Quantity/value",
        )
        self.assertEqual(sorted(v), [0.0, 0.3, 4.27, 9.14])
        v = resolver.resolve_xpath(
            "gw_geologylogcoverage",
            "id",
            "ab.ww.402557.log.1.coverage",
            "element/LogValue/toDepth/Quantity/value",
        )
        self.assertEqual(sorted(v), [0.3, 4.27, 9.14, 11.58])

    def test_timeseries(self):
        resolver = GmlAsXPathResolver("timeseries1.sqlite", "SQLite", "")
        v = resolver.resolve_xpath(
            "measurementtimeseries",
            "id",
            "timeseries.927B7F661CE9CF9F3BF931A87E119E524A5B328F",
            "point/MeasurementTVP/time/text()",
        )
        self.assertEqual(len(v), 5000)
        v = resolver.resolve_xpath(
            "measurementtimeseries",
            "id",
            "timeseries.927B7F661CE9CF9F3BF931A87E119E524A5B328F",
            "defaultPointMetadata/DefaultTVPMeasurementMetadata/interpolationType/@xlink:title",
        )
        self.assertEqual(v, ["Instantaneous"])
        v = resolver.resolve_xpath(
            "measurementtimeseries",
            "id",
            "timeseries.927B7F661CE9CF9F3BF931A87E119E524A5B328F",
            "defaultPointMetadata/DefaultTVPMeasurementMetadata/uom/@code",
        )
        self.assertEqual(v, ["m"])


# ############################################################################
# ####### Stand-alone run ########
# ################################
if __name__ == "__main__":
    unittest.main()
