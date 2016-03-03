#!/usr/bin/env python
# -*- coding: utf-8 -*-

from lxml import etree
from osgeo import ogr
from PyQt4.QtCore import QVariant
import re

def noPrefix(tag):
    if tag.startswith('{'):
        return tag[tag.rfind('}')+1:]
    return tag

def wkbFromGml(tree):
    # extract the srid
    srid = None
    for k, v in tree.attrib.iteritems():
        if noPrefix(k) == 'srsName':
            # EPSG:4326
		  	# urn:EPSG:geographicCRS:4326
		  	# urn:ogc:def:crs:EPSG:4326
		 	# urn:ogc:def:crs:EPSG::4326
		  	# urn:ogc:def:crs:EPSG:6.6:4326
		   	# urn:x-ogc:def:crs:EPSG:6.6:4326
			# http://www.opengis.net/gml/srs/epsg.xml#4326
			# http://www.epsg.org/6.11.2/4326
            # get the last number
            m = re.search('[0-9]+$', v)
            srid = m.group(0)
            break
            
    # call ogr for GML parsing
    s = etree.tostring(tree)
    g = ogr.CreateGeometryFromGML(s)
    return (g.ExportToWkb(), srid)

def extractGmlGeometry(tree):
    if tree.prefix == "gml":
        if noPrefix(tree.tag) in ["Point", "LineString", "Polygon",
                                  "MultiPoint", "MultiCurve", "MultiSurface",
                                  "Curve", "OrientableCurve", "Surface", 
                                  "CompositeCurve", "CompositeSurface", "MultiGeometry"]:
            return wkbFromGml(tree)
        
    for child in tree:
        g = extractGmlGeometry(child)
        if g is not None:
            return g
    return None

class ComplexFeatureSource:
    def __init__(self, xml_file, xpath_mapping = {}):
        """
        Construct a ComplexFeatureSource

        :param xml_file: The input XML file name
        :param xpath_mapping: A mapping of XPath expressions to attributes. Example: { 'attribute' : ('//xpath/expression', QVariant.Int) }
        """
        
        doc = etree.parse(open(xml_file))
        self.root = doc.getroot()
        if self.root.nsmap[self.root.prefix] != "http://www.opengis.net/wfs/2.0":
            raise RuntimeError("only wfs 2 streams are supported for now")
        self.xpath_mapping = xpath_mapping

        if len(self.root) > 0 and len(self.root[0]) > 0:
            self.title = noPrefix(self.root[0][0].tag)
        else:
            self.title = "Complex Features"

    def getFeatures(self):
        """
        The iterator that will yield a new feature.
        The yielded value is (feature_id, QgsGeometry or None, xml_tree: Element, { 'attr1' : value, 'attr2' : 'value' })
        """
        for child in self.root:
            # get the id
            fid = None
            for k, v in child[0].attrib.iteritems():
                if noPrefix(k) == "id":
                    fid = v

            # get the geometry
            wkb = extractGmlGeometry(child[0])

            # get attribute values
            attrvalues = {}
            for attr, xpath_t in self.xpath_mapping.iteritems():
                xpath, type = xpath_t
                r = child.xpath(xpath, namespaces = child.nsmap)
                v = None
                if len(r) > 0:
                    if isinstance(r[0], unicode):
                        v = r[0]
                    if isinstance(r[0], str):
                        v = unicode(r[0])
                    elif isinstance(r[0], etree._Element):
                        v = r[0].text
                    else:
                        v = None
                try:
                    if type == QVariant.Int:
                        value = int(v)
                    elif type == QVariant.String:
                        value = v
                    elif type == QVariant.Double:
                        value = float(v)
                    else:
                        value = None
                except ValueError:
                    value = None
                attrvalues[attr] = value

            yield fid, wkb, child[0], attrvalues


if __name__ == '__main__':
    src = ComplexFeatureSource( "/home/hme/src/brgm_gml/samples/airquality.xml", { 'mainEmissionSources' : ('.//aqd:mainEmissionSources/@xlink:href', QVariant.String),
                                                                                   'stationClassification' : ('.//aqd:stationClassification/@xlink:href', QVariant.String) })
    for x in src.getFeatures():
        print x
