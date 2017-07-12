# -*- coding: utf-8 -*-
# launch it with something like
# QGIS_DEBUG=0 QGIS_PREFIX_PATH=/home/hme/src/QGIS/build/output PYTHONPATH=/home/hme/src/QGIS/build/output/python python3 test_load_in_qgis.py

import qgis
from qgis.testing import start_app, unittest
from qgis.core import QgsCoordinateReferenceSystem

from osgeo import ogr, osr, gdal

import os
import sys
import tempfile

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "gml_application_schema_toolbox"))

from core.load_gmlas_in_qgis import *

start_app()

def convert_and_import(xml_file):
    with tempfile.NamedTemporaryFile(delete=True) as f:
        out_f = f.name
    print(out_f)
    config_file = os.path.join(os.path.dirname(__file__), "gmlasconf.xml")
    gdal.SetConfigOption("OGR_SQLITE_SYNCHRONOUS", "OFF")
    ds = gdal.OpenEx("GMLAS:{}".format(xml_file), open_options=['EXPOSE_METADATA_LAYERS=YES', 'CONFIG_FILE={}'.format(config_file)])
    srs = osr.SpatialReference()
    qgs_srs = QgsCoordinateReferenceSystem("EPSG:4326")
    srs.ImportFromWkt(qgs_srs.toWkt())
    params = {
        'destNameOrDestDS': out_f
        , 'srcDS': ds
        , 'format': "SQLite"
        , 'accessMode': "overwrite"
        , 'datasetCreationOptions': ['SPATIALITE=YES']
        , 'options' : ['-forceNullable', '-skipfailures']
        #, 'srcSRS': srs
        #, 'dstSRS': srs
        , 'geometryType': 'CONVERT_TO_LINEAR'
        , 'reproject': False
    }
    # call gdal to convert
    gdal.VectorTranslate(**params)
    # fix geometry types
    ds = None
    # populate the qgis project
    import_in_qgis(out_f, "SQLite")

    layers = []
    for lid in sorted(QgsProject.instance().mapLayers().keys()):
        vl = QgsProject.instance().mapLayer(lid)
        layers.append((vl.name(), vl.wkbType()))
    rels = []
    relations = QgsProject.instance().relationManager().relations()
    for relid in sorted(relations.keys()):
        rel = relations[relid]
        p = rel.fieldPairs()
        rels.append((rel.id()[0:3], rel.referencingLayer().name(), list(p.keys())[0], rel.referencedLayer().name(), list(p.values())[0]))

    return sorted(layers), sorted(rels)

class TestLoadInQGIS(unittest.TestCase):

    def xtest_1(self):
        f = os.path.join(os.path.dirname(__file__), "..", "samples", "BRGM_raw_database_observation_waterml2_output.xml")
        layers = [('defaulttvpmeasurementmetadata', 100),
                  ('measurementtimeseries', 100),
                  ('measurementtimeseries_defaultpointmetadata', 100),
                  ('measurementtimeseries_point', 100),
                  ('measurementtimeseriesmetadata', 100),
                  ('monitoringpoint', 1),
                  ('monitoringpoint_name', 100),
                  ('monitoringpoint_sampledfeature', 100),
                  ('namedvalue', 100),
                  ('om_observation', 100),
                  ('om_observation_parameter', 100),
                  ('temporalextent', 100),
                  ('timeinstant', 100),
                  ('timeperiod', 100)]
        relations = sorted([('1_1', 'measurementtimeseries', 'metadata_timeseriemetadata_measurementimeseriesmetadata_pkid', 'measurementtimeseriesmetadata', 'ogr_pkid'),
                            ('1_1', 'measurementtimeseries_defaultpointmetadata', 'defaulttvpmetadata_defaulttvpmeasurementmetadata_pkid', 'defaulttvpmeasurementmetadata', 'ogr_pkid'),
                            ('1_1', 'measurementtimeseriesmetadata', 'temporalextent_pkid', 'temporalextent', 'ogr_pkid'),
                            ('1_1', 'om_observation', 'featureofinterest_abstractfeature_monitoringpoint_pkid', 'monitoringpoint', 'id'),
                            ('1_1', 'om_observation', 'phenomenontime_abstracttimeobject_timeperiod_pkid', 'timeperiod', 'id'),
                            ('1_1', 'om_observation', 'result_measurementtimeseries_pkid', 'measurementtimeseries', 'id'),
                            ('1_1', 'om_observation', 'resulttime_timeinstant_pkid', 'timeinstant', 'id'),
                            ('1_1', 'om_observation_parameter', 'namedvalue_pkid', 'namedvalue', 'ogr_pkid'),
                            ('1_n', 'measurementtimeseries_defaultpointmetadata', 'parent_id', 'measurementtimeseries', 'id'),
                            ('1_n', 'measurementtimeseries_point', 'parent_id', 'measurementtimeseries', 'id'),
                            ('1_n', 'monitoringpoint_name', 'parent_id', 'monitoringpoint', 'id'),
                            ('1_n', 'monitoringpoint_sampledfeature', 'parent_id', 'monitoringpoint', 'id'),
                            ('1_n', 'om_observation_parameter', 'parent_id', 'om_observation', 'id')])
        imported_layers, imported_relations = convert_and_import(f)
        self.assertCountEqual(imported_layers, layers)
        self.assertListEqual(imported_layers, layers)
        self.assertCountEqual(imported_relations, relations)
        self.assertListEqual(imported_relations, relations)

    def test_multiple_geometries(self):
        # Test streams that result in layers with multiple geometries
        f = os.path.join(os.path.dirname(__file__), "..", "samples", "EUReg.example.xml")
        layers = sorted([('competentauthority', 100),
                         ('eureg_productioninstallation', 1),
                         ('eureg_productioninstallation (surfacegeometry)', 3),
                         ('eureg_productioninstallation_competentauthorityinspections', 100),
                         ('eureg_productioninstallation_competentauthoritypermits', 100),
                         ('eureg_productioninstallation_groupedinstallationpart', 100),
                         ('eureg_productioninstallation_otherrelevantchapters', 100),
                         ('eureg_productioninstallation_status_status', 100),
                         ('eureg_productioninstallationpart', 1),
                         ('eureg_productioninstallationpart (surfacegeometry)', 3),
                         ('eureg_productioninstallationpart_status', 100),
                         ('eureg_productionsite', 1),
                         ('eureg_productionsite (geometry)', 6),
                         ('eureg_productionsite_status', 100),
                         ('pf_inspireid', 100),
                         ('productionfacility', 1),
                         ('productionfacility (surfacegeometry)', 3),
                         ('productionfacility_competentauthorityeprtr', 100),
                         ('productionfacility_eprtrannexiac_eprtrannexiac_otheractivity', 100),
                         ('productionfacility_function', 100),
                         ('productionfacility_function_function_activity', 100),
                         ('productionfacility_groupedinstallation', 100),
                         ('productionfacility_status', 100),
                         ('reportdata', 100),
                         ('status', 100),
                         ('type', 100)])
        imported_layers, imported_relations = convert_and_import(f)
        #print(layers)
        print(imported_layers)
        self.assertEqual(len(imported_layers), len(layers))
        self.assertListEqual(imported_layers, layers)

    def xtest_postgis(self):
        f = os.path.join(os.path.dirname(__file__), "..", "samples", "gmlas.sqlite")
        import_in_qgis("dbname='test_gmlas' port=5434", "postgres", schema="piezo")
        QgsProject.instance().write("test.qgs")

if __name__ == '__main__':
    unittest.main()
