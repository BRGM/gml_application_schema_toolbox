#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import logging
logging.basicConfig()

import os
import sys
sys.path = [os.path.join(os.path.dirname(__file__), "pyxb")] + sys.path

from schema_parser import parse_schemas
from type_resolver import resolve_types, type_definition_name
from xml_utils import no_prefix, split_tag
from relational_model_builder import load_gml_model

from sqlite_writer import create_sqlite_from_model
from qgis_project_writer import create_qgis_project_from_model

import sys
import urllib2

import xml.etree.ElementTree as ET

import pickle

        
def print_etree(node, type_info_dict, indent = 0):
    ti = type_info_dict[node]
    td = ti.type_info().typeDefinition()
    print(" "*indent, no_prefix(node.tag), "type:", type_definition_name(td), end="")
    if ti.max_occurs() is None:
        print("[]")
    else:
        print()
    for n, t in ti.attribute_type_info_map().iteritems():
        print(" "*indent, "  @" + no_prefix(n), "type:", type_definition_name(t.attributeDeclaration().typeDefinition()))
    for child in node:
        print_etree(child, type_info_dict, indent + 2)



if len(sys.argv) < 3:
    print("Argument: [xsd_files] xml_file sqlite_file")
    exit(1)

xsd_files = sys.argv[1:-2]
xml_file = sys.argv[-2]
sqlite_file = sys.argv[-1]

archive_dir = "archive/"

model = load_gml_model(xml_file, archive_dir, xsd_files)

if os.path.exists(sqlite_file):
    print("SQlite file already exists")
else:
    create_sqlite_from_model(model, sqlite_file)

qgis_file = sqlite_file.replace(".sqlite", ".qgs")

create_qgis_project_from_model(model, sqlite_file, qgis_file)
