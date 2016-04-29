#!/usr/bin/env python
# -*- coding: utf-8 -*-

from lxml import etree
from osgeo import ogr
from PyQt4.QtCore import QVariant

from qgis.core import QGis, QgsGeometry, QgsVectorLayer, QgsField, QgsFeature, QgsMapLayer, QgsDataSourceURI

from pyspatialite import dbapi2 as sqlite3

from qgis_urlopener import remote_open_from_qgis

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
    def __init__(self, xml, xpath_mapping = {}, geometry_mapping = None):
        """
        Construct a ComplexFeatureSource

        :param xml: The input XML, as file io
        :param xpath_mapping: A mapping of XPath expressions to attributes. Example: { 'attribute' : ('//xpath/expression', QVariant.Int) }
        :param geometry_mapping: An XPath expression used to extract the geometry
        """
        doc = etree.parse(xml)
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


class ComplexFeatureLoader:
    """Allows to load a complex feature source and put features in a QGIS layer"""

    def _create_layer(self, geometry_type, srid, attributes, title):
        raise RuntimeError("No default implementation, use a derived class")

    def _add_properties_to_layer(self, layer, xml_uri, is_remote, attributes, geom_mapping):
        raise RuntimeError("No default implementation, use a derived class")

    @staticmethod
    def properties_from_layer(layer):
        raise RuntimeError("No default implementation, use a derived class")

    @staticmethod
    def is_layer_complex(layer):
        raise RuntimeError("No default implementation, use a derived class")

    def load_complex_gml(self, xml_uri, is_remote, attributes = {}, geometry_mapping = None):
        """
        :param xml_uri: the XML URI
        :param is_remote: True if it has to be fetched by http
        :param attributes: { 'attr1' : ( '//xpath/expression', QVariant.Int ) }
        :param geometry_mapping: XPath expression to a gml geometry node
        :returns: the created layer
        """
        if is_remote:
            xml = remote_open_from_qgis(xml_uri)
        else:
            xml = open(xml_uri)
        src = ComplexFeatureSource(xml, attributes, geometry_mapping)

        layer = None
        attr_list = [ (k, v[1]) for k, v in attributes.iteritems() ]
        for fid, g, xml, attrs in src.getFeatures():
            qgsgeom = None
            if g is None:
                if layer is None:
                    layer = self._create_layer('none', None, attr_list, src.title)
            else:
                wkb, srid = g
                qgsgeom = QgsGeometry()
                qgsgeom.fromWkb(wkb)
                if qgsgeom and qgsgeom.type() == QGis.Point:
                    if layer is None:
                        layer = self._create_layer('point', srid, attr_list, src.title + " (points)")
                elif qgsgeom and qgsgeom.type() == QGis.Line:
                    if layer is None:
                        layer = self._create_layer('linestring', srid, attr_list, src.title + " (lines)")
                elif qgsgeom and qgsgeom.type() == QGis.Polygon:
                    if layer is None:
                        layer = self._create_layer('polygon', srid, attr_list, src.title + " (polygons)")

            if layer:
                self._add_properties_to_layer(layer, xml_uri, is_remote, attributes, geometry_mapping)

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

class ComplexFeatureLoaderInMemory(ComplexFeatureLoader):

    def _create_layer(self, geometry_type, srid, attributes, title):
        """
        Creates an empty memory layer
        :param type: 'Point', 'LineString', 'Polygon', etc.
        :param srid: CRS ID of the layer
        :param attributes: list of (attribute_name, attribute_type)
        :param title: title of the layer
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

    def _add_properties_to_layer(self, layer, xml_uri, is_remote, attributes, geom_mapping):
        layer.setCustomProperty("complex_features", True)
        layer.setCustomProperty("xml_uri", xml_uri)
        layer.setCustomProperty("is_remote", is_remote)
        layer.setCustomProperty("attributes", attributes)
        layer.setCustomProperty("geom_mapping", geom_mapping)
        
    @staticmethod
    def properties_from_layer(layer):
        return (layer.customProperty("complex_features", False),
                layer.customProperty("xml_uri", ""),
                layer.customProperty("is_remote", False),
                layer.customProperty("attributes", {}),
                layer.customProperty("geom_mapping", None),
                None #output filename
        )

    @staticmethod
    def is_layer_complex(layer):
        return layer.type() == QgsMapLayer.VectorLayer and layer.customProperty("complex_features", False)


class ComplexFeatureLoaderInSpatialite(ComplexFeatureLoader):

    def __init__(self, output_local_file):
        """
        :param output_local_file: name of the local sqlite file
        """
        self.output_local_file = output_local_file

    def _create_layer(self, type, srid, attributes, title):
        """
        Creates an empty spatialite layer
        :param type: 'Point', 'LineString', 'Polygon', etc.
        :param srid: CRS ID of the layer
        :param attributes: list of (attribute_name, attribute_type)
        :param title: title of the layer
        """
        conn = sqlite3.connect(self.output_local_file)
        cur = conn.cursor()
        cur.execute("SELECT InitSpatialMetadata(1)")
        cur.execute("DROP TABLE IF EXISTS meta")
        cur.execute("DROP TABLE IF EXISTS data")
        cur.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        cur.execute("CREATE TABLE data (id TEXT NOT NULL PRIMARY KEY)")
        if srid:
            cur.execute("SELECT AddGeometryColumn('data', 'geometry', {}, '{}', 'XY')".format(srid, type))
        conn.close()

        if srid:
            layer = QgsVectorLayer("dbname='{}' table=\"data\" (geometry) sql=".format(self.output_local_file), title, "spatialite")
        else:
            layer = QgsVectorLayer("dbname='{}' table=\"data\" sql=".format(self.output_local_file), title, "spatialite")

        pr = layer.dataProvider()
        pr.addAttributes([QgsField("_xml_", QVariant.String)])
        for aname, atype in attributes:
            pr.addAttributes([QgsField(aname, atype)])
        layer.updateFields()
        return layer

    def _add_properties_to_layer(self, layer, xml_uri, is_remote, attributes, geom_mapping):
        import json
        conn = sqlite3.connect(self.output_local_file)
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO meta VALUES('complex_features', '1')")
        cur.execute("INSERT OR REPLACE INTO meta VALUES('xml_uri', ?)", (xml_uri,))
        cur.execute("INSERT OR REPLACE INTO meta VALUES('is_remote', ?)", ('1' if is_remote else '0',))
        cur.execute("INSERT OR REPLACE INTO meta VALUES('attributes', ?)", (json.dumps(attributes),))
        cur.execute("INSERT OR REPLACE INTO meta VALUES('geom_mapping', ?)", (json.dumps(geom_mapping),))
        cur.execute("INSERT OR REPLACE INTO meta VALUES('output_filename', ?)", (self.output_local_file,))
        conn.commit()

    @staticmethod
    def properties_from_layer(layer):
        import json
        nil = (False, None, None, None, None, None)
        if layer.type() != QgsMapLayer.VectorLayer:
            return nil
        if layer.providerType() != "spatialite":
            return nil
        u = QgsDataSourceURI(layer.source())
        conn = sqlite3.connect(u.database())
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM meta")
            ret = list(nil)
            for r in cur:
                if r[0] == 'complex_features':
                    ret[0] = r[1] == '1'
                elif r[0] == 'xml_uri':
                    ret[1] = r[1]
                elif r[0] == 'is_remote':
                    ret[2] = r[1] == '1'
                elif r[0] == 'attributes':
                    ret[3] = json.loads(r[1])
                elif r[0] == 'geom_mapping':
                    ret[4] = json.loads(r[1])
                elif r[0] == 'output_filename':
                    ret[5] = r[1]
            return ret
        except sqlite3.OperationalError:
            return False, None, None, None, None, None

    @staticmethod
    def is_layer_complex(layer):
        if layer.type() != QgsMapLayer.VectorLayer:
            return False
        if layer.providerType() != "spatialite":
            return False
        u = QgsDataSourceURI(layer.source())
        conn = sqlite3.connect(u.database())
        cur = conn.cursor()
        cur.execute("SELECT value FROM meta WHERE key='complex_features'")
        for r in cur:
            return r[0] == '1'
        return False

def load_complex_gml(xml_uri, is_remote, attributes = {}, geometry_mapping = None, output_local_file = None):
    if not output_local_file:
        import tempfile
        f = tempfile.NamedTemporaryFile()
        output_local_file = f.name
        f.close()

    s = ComplexFeatureLoaderInSpatialite(output_local_file)
    return s.load_complex_gml(xml_uri, is_remote, attributes, geometry_mapping)

def properties_from_layer(layer):
    return ComplexFeatureLoaderInSpatialite.properties_from_layer(layer)

def is_layer_complex(layer):
    return ComplexFeatureLoaderInSpatialite.is_layer_complex(layer)

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

