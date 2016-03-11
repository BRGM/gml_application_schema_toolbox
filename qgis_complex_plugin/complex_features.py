#!/usr/bin/env python
# -*- coding: utf-8 -*-

from lxml import etree
from osgeo import ogr
from PyQt4.QtCore import QVariant

from qgis.core import QGis, QgsGeometry, QgsVectorLayer, QgsField, QgsFeature

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
            m = re.search('([0-9]+)/?$', v)
            srid = m.group(1)
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

def extractGmlFromXPath(tree, xpath):
    r = tree.xpath("./" + xpath, namespaces = tree.nsmap)
    if len(r) > 0:
        return wkbFromGml(r[0])
    return None

class ComplexFeatureSource:
    def __init__(self, xml_file, xpath_mapping = {}, geometry_mapping = None):
        """
        Construct a ComplexFeatureSource

        :param xml_file: The input XML file name
        :param xpath_mapping: A mapping of XPath expressions to attributes. Example: { 'attribute' : ('//xpath/expression', QVariant.Int) }
        :param geometry_mapping: An XPath expression used to extract the geometry
        """
        
        doc = etree.parse(open(xml_file))
        root = doc.getroot()
        if noPrefix(root.tag) != 'FeatureCollection':
            # this seems to be an isolated feature
            self.features = [root]
            self.title = noPrefix(root.tag)
        else:
            self.features = root.xpath("/wfs:FeatureCollection/wfs:member/*", namespaces = root.nsmap)
            if len(self.features) == 0:
                self.features = root.xpath("/wfs:FeatureCollection/gml:featureMembers/*", namespaces = root.nsmap)
                if len(self.features) == 0:
                    raise RuntimeError("Unrecognized XML file")

            self.title = noPrefix(self.features[0].tag)

        self.xpath_mapping = xpath_mapping
        self.geometry_mapping = geometry_mapping

    def getFeatures(self):
        """
        The iterator that will yield a new feature.
        The yielded value is (feature_id, QgsGeometry or None, xml_tree: Element, { 'attr1' : value, 'attr2' : 'value' })
        """
        i = 1
        for feature in self.features:
            # get the id from gml:identifier
            fid = unicode(i)
            if feature.nsmap.has_key('gml'):
                x = feature.xpath(".//gml:identifier/text()", namespaces = feature.nsmap)
                if len(x) > 0:
                    fid = unicode(x[0])

            # get the geometry
            if self.geometry_mapping:
                wkb = extractGmlFromXPath(feature, self.geometry_mapping)
            else:
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
            i += 1

def create_memory_layer(type, srid, attributes, title):
    """
    Creates an empty memory layer
    :param type: 'Point', 'LineString', 'Polygon', etc.
    :param srid: CRS ID of the layer
    :param attributes: list of (attribute_name, attribute_type)
    """
    if srid:
        layer = QgsVectorLayer("{}?crs=EPSG:{}&field=id:string".format(type, srid), title, "memory")
    else:
        layer = QgsVectorLayer("none?field=id:string", title, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([QgsField("_xml_", QVariant.String)])
    for aname, atype in attributes:
        pr.addAttributes([QgsField(aname, atype)])
    layer.updateFields()
    return layer

def add_properties_to_layer(layer, xml_uri, is_remote, attributes, geom_mapping):
    layer.setCustomProperty("complex_features", True)
    layer.setCustomProperty("xml_uri", xml_uri)
    layer.setCustomProperty("is_remote", is_remote)
    layer.setCustomProperty("attributes", attributes)
    layer.setCustomProperty("geom_mapping", geom_mapping)

def properties_from_layer(layer):
    return (layer.customProperty("complex_features", False),
            layer.customProperty("xml_uri", ""),
            layer.customProperty("is_remote", False),
            layer.customProperty("attributes", {}),
            layer.customProperty("geom_mapping", None)
    )

def is_layer_complex(layer):
    return layer.customProperty("complex_features", False)

def load_complex_gml(xml_uri, is_remote, attributes = {}, geometry_mapping = None):
    """
    :param xml_uri: the XML URI
    :param is_remote: True if it has to be fetched by http
    :param attributes: { 'attr1' : ( '//xpath/expression', QVariant.Int ) }
    :param geometry_mapping: XPath expression to a gml geometry node
    :returns: the created layer
    """
    if is_remote:
        import urllib
        xml_file, _ = urllib.urlretrieve(xml_uri)
    else:
        xml_file = xml_uri
    src = ComplexFeatureSource(xml_file, attributes, geometry_mapping)

    layer = None
    for fid, g, xml, attrs in src.getFeatures():
        qgsgeom = None
        if g is None:
            if layer is None:
                layer = createMemoryLayer('none', None, [ (k, v[1]) for k, v in attributes.iteritems() ], src.title)
        else:
            wkb, srid = g
            qgsgeom = QgsGeometry()
            qgsgeom.fromWkb(wkb)
            if qgsgeom and qgsgeom.type() == QGis.Point:
                if layer is None:
                    layer = create_memory_layer('point', srid, [ (k, v[1]) for k, v in attributes.iteritems() ], src.title + " (points)")
            elif qgsgeom and qgsgeom.type() == QGis.Line:
                if layer is None:
                    layer = create_memory_layer('linestring', srid, [ (k, v[1]) for k, v in attributes.iteritems() ], src.title + " (lines)")
            elif qgsgeom and qgsgeom.type() == QGis.Polygon:
                if layer is None:
                    layer = create_memory_layer('polygon', srid, [ (k, v[1]) for k, v in attributes.iteritems() ], src.title + " (polygons)")

        if layer:
            add_properties_to_layer(layer, xml_uri, is_remote, attributes, geometry_mapping)

            pr = layer.dataProvider()
            f = QgsFeature(pr.fields())
            if qgsgeom:
                f.setGeometry(qgsgeom)
            f.setAttribute("id", fid)
            f.setAttribute("_xml_", etree.tostring(xml))
            for k, v in attrs.iteritems():
                r = f.setAttribute(k, v)
            pr.addFeatures([f])

    return layer

if __name__ == '__main__':
    print "GSML4"
    src = ComplexFeatureSource( "../samples/GSML4-Borehole.xml", geometry_mapping = "/gsmlbh:location/gml:Point")
    for x in src.getFeatures():
        print x
        
    print("mineral")
    src = ComplexFeatureSource( "../samples/mineral.xml")
    for x in src.getFeatures():
        print x

    print("Boreholeview")
    src = ComplexFeatureSource( "../samples/BoreholeView.xml")
    for x in src.getFeatures():
        print x

    print("airquality")
    src = ComplexFeatureSource( "../samples/airquality.xml", { 'mainEmissionSources' : ('.//aqd:mainEmissionSources/@xlink:href', QVariant.String),
                                                               'stationClassification' : ('.//aqd:stationClassification/@xlink:href', QVariant.String) })
    for x in src.getFeatures():
        print x

    print("env_monitoring")
    src = ComplexFeatureSource( "../samples/env_monitoring.xml")
    for x in src.getFeatures():
        print x

    print("env_monitoring1")
    src = ComplexFeatureSource( "../samples/env_monitoring1.xml")
    for x in src.getFeatures():
        print x

