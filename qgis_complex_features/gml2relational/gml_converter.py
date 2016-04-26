#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import logging
from optparse import OptionParser

import os
import sys
sys.path = [os.path.join(os.path.dirname(__file__), "../whl/all")] + sys.path

from schema_parser import parse_schemas
from type_resolver import resolve_types, type_definition_name
from xml_utils import no_prefix, split_tag
from relational_model_builder import load_gml_model

from sqlite_writer import create_sqlite_from_model
from qgis_project_writer import create_qgis_project_from_model

parser = OptionParser()
parser.add_option("-i", "--gml", dest="gml_file",
                  help="input GML file", metavar="GML_FILE")
parser.add_option("--archive-dir", dest="archive_dir", default = "/tmp", 
                  help="specify the directory where XSD and model files are cached")
parser.add_option("-s", "--output-spatialite",
                  dest="sqlite_file", default=None,
                  help="generate a Spatialite file from the model")
parser.add_option("-q", "--output-qgis",
                  dest="qgis_file", default=None,
                  help="generate a QGIS project file from the model")
parser.add_option("--srs-db",
                  dest="srs_db", default="/tmp/srs.db",
                  help="location of the QGIS SRS database")
parser.add_option("--merge-depth",
                  dest="merge_depth", default=6, type="int",
                  help="maximum depth to consider when merging tables")
parser.add_option('-V', action="store_true", dest="verbose",
                  help="enable verbose output")
parser.add_option('--debug', action="store_true", dest="debug",
                  help="enable debug verbose output")

(options, args) = parser.parse_args()

if options.gml_file is None:
    print("No input GML file. Abort")
    exit(1)

print("Input file: {}".format(options.gml_file))
print("Archive directory: {}".format(options.archive_dir))
print("Merge max depth: {}".format(options.merge_depth))

level = logging.WARNING
if options.verbose:
    level = logging.INFO
if options.debug:
    level = logging.DEBUG
logging.basicConfig(format='%(message)s', level = level)

model = load_gml_model(options.gml_file, options.archive_dir, [], options.merge_depth)

if options.sqlite_file is not None:
    print("Spatialite output file: {}".format(options.sqlite_file))
    if os.path.exists(options.sqlite_file):
        print("Spatialite file already exists")
    else:
        create_sqlite_from_model(model, options.sqlite_file)

    if options.qgis_file is not None:
        print("QGIS project file: {}".format(options.qgis_file))
        create_qgis_project_from_model(model, options.sqlite_file, options.qgis_file, options.srs_db)
