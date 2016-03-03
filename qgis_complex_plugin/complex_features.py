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
        root = doc.getroot()
        if noPrefix(root.tag) != 'FeatureCollection':
            # this seems to be an isolated feature
            self.features = [root]
            self.title = noPrefix(root.tag)
        else:
            if len(root) > 0 and noPrefix(root[0].tag) == 'member':
                self.title = noPrefix(root[0][0].tag)
                self.features = [x[0] for x in root]
            elif len(root) > 0 and noPrefix(root[0].tag) == "featureMembers":
                self.title = noPrefix(root[0][0].tag)
                self.features = root[0]
            else:
                raise RuntimeError("Unrecognized XML file")

        self.xpath_mapping = xpath_mapping

    def getFeatures(self):
        """
        The iterator that will yield a new feature.
        The yielded value is (feature_id, QgsGeometry or None, xml_tree: Element, { 'attr1' : value, 'attr2' : 'value' })
        """
        for feature in self.features:
            # get the id
            fid = None
            for k, v in feature.attrib.iteritems():
                if noPrefix(k) == "id":
                    fid = v

            # get the geometry
            wkb = extractGmlGeometry(feature)

            # get attribute values
            attrvalues = {}
            for attr, xpath_t in self.xpath_mapping.iteritems():
                xpath, type = xpath_t
                # resolve xpath
                r = feature.xpath("./" + xpath, namespaces = feature.nsmap)
                v = None
                value = None
                if len(r) > 0:
                    if isinstance(r[0], unicode):
                        v = r[0]
                    if isinstance(r[0], str):
                        v = unicode(r[0])
                    elif isinstance(r[0], etree._Element):
                        v = r[0].text
                    else:
                        v = None
                        value = None
                if v is not None:
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

            yield fid, wkb, feature, attrvalues


if __name__ == '__main__':
    src = ComplexFeatureSource( "../samples/airquality.xml", { 'mainEmissionSources' : ('.//aqd:mainEmissionSources/@xlink:href', QVariant.String),
                                                               'stationClassification' : ('.//aqd:stationClassification/@xlink:href', QVariant.String) })
    for x in src.getFeatures():
        print x

    src = ComplexFeatureSource( "../samples/env_monitoring.xml")
    for x in src.getFeatures():
        print x

    src = ComplexFeatureSource( "../samples/env_monitoring1.xml")
    for x in src.getFeatures():
        print x

    src = ComplexFeatureSource( "../samples/BoreholeView.xml")
    for x in src.getFeatures():
        print x

