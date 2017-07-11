# -*- coding: utf-8 -*-
# launch it with something like
# QGIS_DEBUG=0 QGIS_PREFIX_PATH=/home/hme/src/QGIS/build/output PYTHONPATH=/home/hme/src/QGIS/build/output/python python3 test_load_in_qgis.py

import qgis
from qgis.testing import start_app, unittest
from qgis.core import QgsCoordinateReferenceSystem

from osgeo import ogr, osr, gdal

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "gml_application_schema_toolbox"))

from core.load_gmlas_in_qgis import *
from core.fix_geometry_types import fix_geometry_types_in_spatialite

start_app()

def convert_and_import(xml_file):
    out_f = "/tmp/t.sqlite"
    config_file = os.path.join(os.path.dirname(__file__), "gmlasconf.xml")
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
        # FIXME
        #, 'srcSRS': srs
        , 'dstSRS': srs
        , 'geometryType': 'CONVERT_TO_LINEAR'
        , 'reproject': True
    }
    # call gdal to convert
    gdal.VectorTranslate(**params)
    # fix geometry types
    ds = None
    fix_geometry_types_in_spatialite(out_f)
    # populate the qgis project
    import_in_qgis("dbname='{}'".format(out_f), "spatialite")

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

    return layers, rels

class TestLoadInQGIS(unittest.TestCase):

    def test_1(self):
        #f = os.path.join(os.path.dirname(__file__), "..", "samples", "BoreholeView.xml")
        f = os.path.join(os.path.dirname(__file__), "..", "samples", "BRGM_raw_database_observation_waterml2_output.xml")
        #layers = [('boreholeview', 1)]
        #relations = []
        imported_layers, imported_relations = convert_and_import(f)
        #self.assertCountEqual(imported_layers, layers)
        #self.assertListEqual(imported_layers, layers)
        #self.assertCountEqual(imported_relations, relations)
        #self.assertListEqual(imported_relations, relations)

    def xtest_postgis(self):
        f = os.path.join(os.path.dirname(__file__), "..", "samples", "gmlas.sqlite")
        import_in_qgis("dbname='test_gmlas' port=5434", "postgres", schema="piezo")
        QgsProject.instance().write("test.qgs")

if __name__ == '__main__':
    unittest.main()
