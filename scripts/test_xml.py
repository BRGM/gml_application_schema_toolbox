#!/usr/bin/env python

import sys

if len(sys.argv) == 1:
    print "Arguments: schema_file xml_file"
    exit(1)

from lxml import etree
import urllib

class MyResolver(etree.Resolver):
    def resolve(self, url, id, context):
        print url
        return etree.Resolver.resolve( self, url, id, context )


schema_file = sys.argv[1]
xml_file = sys.argv[2]

parser = etree.XMLParser(ns_clean=True)
parser.resolvers.add( MyResolver() )
schema_tree = etree.parse(open(schema_file), parser)
print schema_tree

print "load schema"
xml_schema = etree.XMLSchema(schema_tree)

print "parse XML"
doc = etree.parse(open(xml_file))

print "validate"
xml_schema.assertValid(doc)

if False:
    root = schema_tree.getroot()
    print root.tag

    slist = schema_tree.xpath("//x:import", namespaces = {'x':'http://www.w3.org/2001/XMLSchema'})
    for e in slist:
        print e.attrib

