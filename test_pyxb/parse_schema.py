#!/usr/bin/env python

from __future__ import print_function
import logging
logging.basicConfig()

import sys
sys.path = ['/home/hme/src/pyxb'] + sys.path
print(sys.path)

from pyxb.xmlschema.structures import Schema, ElementDeclaration, ComplexTypeDefinition, Particle, ModelGroup, SimpleTypeDefinition, Wildcard, AttributeUse, AttributeDeclaration

from schema_parser import parse_schemas
from type_resolver import resolve_types, no_prefix, type_definition_name

import os
import sys

def mkdir_p(path):
    """Recursively create all subdirectories of a given path"""
    dirs = path.split('/')
    p = ""
    for d in dirs:
        p = os.path.join(p, d)
        if not os.path.exists(p):
            os.mkdir(p)

class URIResolver(object):
    def __init__(self, cachedir):
        self.__cachedir = cachedir

    def data_from_uri(self, uri):
        if uri.startswith('http://'):
            base_uri = 'http://' + '/'.join(uri[7:].split('/')[:-1])
        else:
            base_uri = os.path.dirname(uri)

        print("Resolving schema {} ... ".format(uri), end="")

        out_file_name = uri
        if uri.startswith('http://'):
            out_file_name = uri[7:]
        out_file_name = os.path.join(self.__cachedir, out_file_name)
        if not os.path.exists(out_file_name):
            f = urllib2.urlopen(uri)
            mkdir_p(os.path.dirname(out_file_name))
            fo = open(out_file_name, "w")
            fo.write(f.read())
            fo.close()
            f.close()
        f = open(out_file_name)
        print("OK")
        return f.read()

def print_etree(node, type_info_dict, indent = 0):
    ti = type_info_dict[node]
    td = ti.type_info().typeDefinition()
    print(" "*indent, no_prefix(node.tag), "type:", type_definition_name(td))
    #if ti.type_info().name() == 'reportedTo':
    #    import ipdb; ipdb.set_trace()
    for n, t in ti.attribute_type_info_map().iteritems():
        print(" "*indent, "  @" + no_prefix(n), "type:", type_definition_name(t.typeDefinition()))
    for child in node:
        print_etree(child, type_info_dict, indent + 2)


if len(sys.argv) < 3:
    print("Argument: xsd_file xml_file")
    exit(1)

xsd_files = sys.argv[1:-1]
xml_file = sys.argv[-1]
    
uri_resolver = URIResolver("archive")

ns = parse_schemas(xsd_files, urlopen = lambda uri : uri_resolver.data_from_uri(uri))
        
import xml.etree.ElementTree as ET
doc = ET.parse(xml_file)

type_info_dict = resolve_types(doc, ns)

print_etree(doc.getroot(), type_info_dict)
