#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import logging
logging.basicConfig()

import sys
sys.path = ['/home/hme/src/pyxb'] + sys.path

from schema_parser import parse_schemas
from type_resolver import resolve_types, type_definition_name
from xml_utils import no_prefix, split_tag
from relational_model_builder import build_tables

from sqlite_writer import create_sqlite_from_model
from qgis_project_writer import qgis_project_from_model

import os
import sys
import urllib2

import xml.etree.ElementTree as ET
# for GML geometry to WKT
from osgeo import ogr

import pickle

class URIResolver(object):
    def __init__(self, cachedir):
        self.__cachedir = cachedir

    def cache_uri(self, uri, parent_uri = '', lvl = 0):
        def mkdir_p(path):
            """Recursively create all subdirectories of a given path"""
            dirs = path.split('/')
            if dirs[0] == '':
                p = '/'
                dirs = dirs[1:]
            else:
                p = ''
            for d in dirs:
                p = os.path.join(p, d)
                if not os.path.exists(p):
                    os.mkdir(p)

        print(" "*lvl, "Resolving schema {} ... ".format(uri))

        if not uri.startswith('http://'):
            if uri.startswith('/'):
                # absolute file name
                return uri
            uri = parent_uri + uri
        base_uri = 'http://' + '/'.join(uri[7:].split('/')[:-1]) + "/"

        out_file_name = uri
        if uri.startswith('http://'):
            out_file_name = uri[7:]
        out_file_name = os.path.join(self.__cachedir, out_file_name)
        if os.path.exists(out_file_name):
            return out_file_name
        
        f = urllib2.urlopen(uri)
        mkdir_p(os.path.dirname(out_file_name))
        fo = open(out_file_name, "w")
        fo.write(f.read())
        fo.close()
        f.close()

        # process imports
        doc = ET.parse(out_file_name)
        root = doc.getroot()

        for child in root:
            n_child_tag = no_prefix(child.tag)
            if n_child_tag == "import" or n_child_tag == "include":
                for an, av in child.attrib.iteritems():
                    if no_prefix(an) == "schemaLocation":
                        self.cache_uri(av, base_uri, lvl+2)
        return out_file_name
    
    def data_from_uri(self, uri):
        out_file_name = self.cache_uri(uri)
        f = open(out_file_name)
        return f.read()
        
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


def extract_features(doc):
    """Extract (Complex) features from a XML doc
    :param doc: a DOM document
    :returns: a list of nodes for each feature
    """
    nodes = []
    root = doc.getroot()
    if root.tag.startswith(u'{http://www.opengis.net/wfs') and root.tag.endswith('FeatureCollection'):
        # WFS features
        for child in root:
            if no_prefix(child.tag) == 'member':
                nodes.append(child[0])
            elif no_prefix(child.tag) == 'featureMembers':
                for cchild in child:
                    nodes.append(cchild)
    else:
        # it seems to be an isolated feature
        nodes.append(root)
    return nodes

if len(sys.argv) < 3:
    print("Argument: [xsd_files] xml_file sqlite_file")
    exit(1)

xsd_files = sys.argv[1:-2]
xml_file = sys.argv[-2]
sqlite_file = sys.argv[-1]

if not os.path.exists("cache.bin"):
    uri_resolver = URIResolver("archive")

    doc = ET.parse(xml_file)
    features = extract_features(doc)
    root = features[0]
    root_ns, root_name = split_tag(root.tag)

    if len(xsd_files) == 0:
        # try to download schemas
        root = doc.getroot()
        for an, av in root.attrib.iteritems():
            if no_prefix(an) == "schemaLocation":
                xsd_files = [uri_resolver.cache_uri(x) for x in av.split()[1::2]]

    if len(xsd_files) == 0:
        print("No schema found, please specify them as arguments")
        exit(1)

    ns_map = parse_schemas(xsd_files, urlopen = lambda uri : uri_resolver.data_from_uri(uri))
    print(xsd_files)
    print(ns_map.keys())
    #exit(0)
    ns = ns_map[root_ns]
    root_type = ns.elementDeclarations()[root_name].typeDefinition()

    #print_etree(doc.getroot(), type_info_dict)

    print("Creating database schema ... ")

    tables = None
    tables_rows = None
    for idx, node in enumerate(features):
        print("+ Feature #{}/{}".format(idx+1, len(features)))
        type_info_dict = resolve_types(node, ns_map)
        tables, tables_rows = build_tables(node, type_info_dict, tables, tables_rows)

    print("OK")

    if False:
        print("Writing cache file ... ")
        fo = open("cache.bin", "w")
        fo.write(pickle.dumps([tables, tables_rows, root_name]))
        fo.close()
else:
    print("Reading from cache file ... ")
    fi = open("cache.bin", "r")
    tables, tables_rows, root_name = pickle.loads(fi.read())


if os.path.exists(sqlite_file):
    print("SQlite file already exists")
else:
    create_sqlite_from_model(tables, tables_rows, sqlite_file)

for table_name, table in tables.iteritems():
    for column in table.columns():
        print(table_name, column.name())

#exit(0)
    
qgis_file = sqlite_file.replace(".sqlite", ".qgs")

qgis_project_from_model(tables, tables_rows, root_name, sqlite_file, qgis_file)
