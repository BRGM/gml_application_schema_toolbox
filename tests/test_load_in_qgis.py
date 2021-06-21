#! python3  # noqa E265

"""
    Usage from the repo root folder:

    Launch it with something like

    `QGIS_DEBUG=0 QGIS_PREFIX_PATH=/home/hme/src/QGIS/build/output PYTHONPATH=/home/hme/src/QGIS/build/output/python python3 test_load_in_qgis.py`

    .. code-block:: bash

        # for whole tests
        python -m unittest tests.test_load_in_qgis
        # for specific test
        python -m unittest tests.test_load_in_qgis.TestLoadInQGIS.test_geologylog
"""

# standard library
import tempfile
from pathlib import Path

# 3rd party
from osgeo import gdal, osr

# PyQGIS
from qgis.core import QgsCoordinateReferenceSystem, QgsProject
from qgis.testing import unittest

# project
from gml_application_schema_toolbox.core.load_gmlas_in_qgis import import_in_qgis


# ############################################################################
# ########## Classes #############
# ################################
class TestLoadInQGIS(unittest.TestCase):
    """Tests."""

    def convert_and_import(self, xml_file):
        # GMLAS configuration file
        config_file = Path("tests/fixtures/gmlasconf.xml")
        self.assertTrue(config_file.is_file())

        # create fixture
        QgsProject.instance().clear()
        with tempfile.NamedTemporaryFile(prefix="qgis_gmlas_", delete=True) as f:
            out_file = f.name

        # open it
        gdal.SetConfigOption("OGR_SQLITE_SYNCHRONOUS", "OFF")
        ds = gdal.OpenEx(
            "GMLAS:{}".format(xml_file),
            open_options=[
                "EXPOSE_METADATA_LAYERS=YES",
                "CONFIG_FILE={}".format(config_file),
            ],
        )

        # SRS
        srs = osr.SpatialReference()
        qgs_srs = QgsCoordinateReferenceSystem("EPSG:4326")
        srs.ImportFromWkt(qgs_srs.toWkt())

        # GDAL vector conversion
        params = {
            "format": "SQLite",
            "accessMode": "overwrite",
            "datasetCreationOptions": ["SPATIALITE=YES"],
            "options": ["-forceNullable", "-skipfailures"]
            # , 'srcSRS': srs
            # , 'dstSRS': srs
            ,
            "geometryType": "CONVERT_TO_LINEAR",
            "reproject": False,
        }
        # call gdal to convert
        gdal.VectorTranslate(destNameOrDestDS=out_file, srcDS=ds, **params)

        # fix geometry types
        # ds = None
        # populate the qgis project
        import_in_qgis(gmlas_uri=out_file, provider="SQLite")

        layers = []
        for lid in sorted(QgsProject.instance().mapLayers().keys()):
            vl = QgsProject.instance().mapLayer(lid)
            layers.append((vl.name(), vl.wkbType()))
        rels = []
        relations = QgsProject.instance().relationManager().relations()
        for relid in sorted(relations.keys()):
            rel = relations[relid]
            p = rel.fieldPairs()
            rels.append(
                (
                    rel.id()[0:3],
                    rel.referencingLayer().name(),
                    list(p.keys())[0],
                    rel.referencedLayer().name(),
                    list(p.values())[0],
                )
            )

        return sorted(layers), sorted(rels)

    def test_load_waterml2(self):
        sample_file = Path(
            "tests/fixtures/BRGM_raw_database_observation_waterml2_output.xml"
        )
        self.assertTrue(sample_file.is_file())

        layers = sorted(
            [
                ("defaulttvpmeasurementmetadata", 100),
                ("measurementtimeseries", 100),
                ("measurementtimeseries_defaultpointmetadata", 100),
                ("measurementtimeseries_point", 100),
                ("measurementtimeseriesmetadata", 100),
                ("monitoringpoint", 1),
                ("monitoringpoint_name", 100),
                ("monitoringpoint_sampledfeature", 100),
                ("namedvalue", 100),
                ("om_observation", 100),
                ("om_observation_parameter", 100),
                ("temporalextent", 100),
                ("timeinstant", 100),
                ("timeperiod", 100),
            ]
        )

        relations = sorted(
            [
                (
                    "1_1",
                    "measurementtimeseries",
                    "metadata_timeseriemetadata_measurementimeseriesmetadata_pkid",
                    "measurementtimeseriesmetadata",
                    "ogr_pkid",
                ),
                (
                    "1_1",
                    "measurementtimeseries_defaultpointmetadata",
                    "defaulttvpmetadata_defaulttvpmeasurementmetadata_pkid",
                    "defaulttvpmeasurementmetadata",
                    "ogr_pkid",
                ),
                (
                    "1_1",
                    "measurementtimeseriesmetadata",
                    "temporalextent_pkid",
                    "temporalextent",
                    "ogr_pkid",
                ),
                (
                    "1_1",
                    "om_observation",
                    "featureofinterest_abstractfeature_monitoringpoint_pkid",
                    "monitoringpoint",
                    "ogr_pkid",
                ),
                (
                    "1_1",
                    "om_observation",
                    "phenomenontime_abstracttimeobject_timeperiod_pkid",
                    "timeperiod",
                    "ogr_pkid",
                ),
                (
                    "1_1",
                    "om_observation",
                    "result_measurementtimeseries_pkid",
                    "measurementtimeseries",
                    "ogr_pkid",
                ),
                (
                    "1_1",
                    "om_observation",
                    "resulttime_timeinstant_pkid",
                    "timeinstant",
                    "ogr_pkid",
                ),
                (
                    "1_1",
                    "om_observation_parameter",
                    "namedvalue_pkid",
                    "namedvalue",
                    "ogr_pkid",
                ),
                (
                    "1_n",
                    "measurementtimeseries_defaultpointmetadata",
                    "parent_ogr_pkid",
                    "measurementtimeseries",
                    "ogr_pkid",
                ),
                (
                    "1_n",
                    "measurementtimeseries_point",
                    "parent_ogr_pkid",
                    "measurementtimeseries",
                    "ogr_pkid",
                ),
                (
                    "1_n",
                    "monitoringpoint_name",
                    "parent_ogr_pkid",
                    "monitoringpoint",
                    "ogr_pkid",
                ),
                (
                    "1_n",
                    "monitoringpoint_sampledfeature",
                    "parent_ogr_pkid",
                    "monitoringpoint",
                    "ogr_pkid",
                ),
                (
                    "1_n",
                    "om_observation_parameter",
                    "parent_ogr_pkid",
                    "om_observation",
                    "ogr_pkid",
                ),
            ]
        )

        imported_layers, imported_relations = self.convert_and_import(sample_file)

        import json

        with open("wl_imported_relations.json", "w") as j:
            json.dump(imported_relations, j)

        self.assertEqual(len(layers), len(imported_layers))
        self.assertListEqual(layers, imported_layers)
        self.assertEqual(len(relations), len(imported_relations))
        self.assertListEqual(relations, imported_relations)

    def test_load_multiple_geometries(self):
        sample_file = Path("tests/fixtures/EUReg.example.xml")
        self.assertTrue(sample_file.is_file())

        layers = sorted(
            [
                ("competentauthority", 100),
                ("eureg_productioninstallation", 1),
                ("eureg_productioninstallation (surfacegeometry)", 3),
                ("eureg_productioninstallation_competentauthorityinspections", 100),
                ("eureg_productioninstallation_competentauthoritypermits", 100),
                ("eureg_productioninstallation_groupedinstallationpart", 100),
                ("eureg_productioninstallation_otherrelevantchapters", 100),
                ("eureg_productioninstallation_status_status", 100),
                ("eureg_productioninstallationpart", 1),
                ("eureg_productioninstallationpart (surfacegeometry)", 3),
                ("eureg_productioninstallationpart_status", 100),
                ("eureg_productionsite", 1),
                ("eureg_productionsite (geometry)", 6),
                ("eureg_productionsite_status", 100),
                ("pf_inspireid", 100),
                ("productionfacility", 1),
                ("productionfacility (surfacegeometry)", 3),
                ("productionfacility_competentauthorityeprtr", 100),
                ("productionfacility_eprtrannexiac_eprtrannexiac_otheractivity", 100),
                ("productionfacility_function", 100),
                ("productionfacility_function_function_activity", 100),
                ("productionfacility_groupedinstallation", 100),
                ("productionfacility_status", 100),
                ("reportdata", 100),
                ("status", 100),
                ("type", 100),
            ]
        )
        imported_layers, imported_relations = self.convert_and_import(sample_file)
        self.assertEqual(len(imported_layers), len(layers))
        self.assertListEqual(imported_layers, layers)

    # def xtest_postgis(self):
    #     import_in_qgis("dbname='test_gmlas' port=5434", "postgres", schema="piezo")
    #     QgsProject.instance().write("test.qgs")


# ############################################################################
# ####### Stand-alone run ########
# ################################
if __name__ == "__main__":
    unittest.main()
