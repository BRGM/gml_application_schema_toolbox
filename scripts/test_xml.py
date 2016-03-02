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

if False:
    parser = etree.XMLParser(ns_clean=True)
    parser.resolvers.add( MyResolver() )
    schema_tree = etree.parse(open(schema_file), parser)
    print schema_tree

    print "load schema"
    xml_schema = etree.XMLSchema(schema_tree)
    print dir(xml_schema)

    print "parse XML"
    doc = etree.parse(open(xml_file))

    print "validate"
    xml_schema.assertValid(doc)

def noPrefix(tag):
    if tag.startswith('{'):
        return tag[tag.rfind('}')+1:]
    return tag
    
def wktFromGmlPoint(tree):
    srsid = None
    for k, v in tree.attrib.iteritems():
        if noPrefix(k) == 'srsName':
            srsid = v[-4:]
    for child in tree:
        if noPrefix(child.tag) == 'pos':
            return "POINT(" + child.text + ")", srsid
    
def extractGmlGeometry(tree):
    if tree.prefix == "gml" and noPrefix(tree.tag) == "Point":
        return wktFromGmlPoint(tree)
    for child in tree:
        g = extractGmlGeometry(child)
        if g is not None:
            return g
    return None
    
class ComplexFeatureSource:
    def __init__(self, xml_file, mapping):
        doc = etree.parse(open(xml_file))
        self.root = doc.getroot()
        if self.root.nsmap[self.root.prefix] != "http://www.opengis.net/wfs/2.0":
            raise RuntimeError("only wfs 2 streams are supported for now")
        self.mapping = mapping
        

    def getFeatures(self):
        for child in self.root:
            print child.tag
            fid = None
            for k, v in child[0].attrib.iteritems():
                if noPrefix(k) == "id":
                    fid = v
            geom = extractGmlGeometry(child[0])

            attrmap = {}
            for attr, xpath in self.mapping.iteritems():
                r = child.xpath(xpath, namespaces = child.nsmap)
                if len(r) > 0:
                    if isinstance(r[0], unicode):
                        attrmap[attr] = r[0]
                    elif isinstance(r[0], etree._Element):
                        attrmap[attr] = r[0].text
            yield fid, geom, child[0], attrmap


src = ComplexFeatureSource(xml_file, { 'inspireId' : './/ef:inspireId//base:localId',
                                       'purpose' : './/ef:purpose/@xlink:title' } )

for id, g, xml, attrmap in src.getFeatures():
    print id, g, xml, attrmap
            
if False:
    root = schema_tree.getroot()
    print root.tag

    slist = schema_tree.xpath("//x:import", namespaces = {'x':'http://www.w3.org/2001/XMLSchema'})
    for e in slist:
        print e.attrib

