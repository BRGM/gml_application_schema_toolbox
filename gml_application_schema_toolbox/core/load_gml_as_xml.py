#!/usr/bin/env python

#   Copyright (C) 2016 BRGM (http:///brgm.fr)
#   Copyright (C) 2016 Oslandia <infos@oslandia.com>
#
#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Library General Public
#   License as published by the Free Software Foundation; either
#   version 2 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Library General Public License for more details.
#   You should have received a copy of the GNU Library General Public
#   License along with this library; if not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
from __future__ import absolute_import
from builtins import str
from builtins import object
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
from osgeo import ogr
import sqlite3
import re

from qgis.PyQt.QtCore import QVariant, QDateTime

from qgis.core import QgsWkbTypes, QgsGeometry, QgsVectorLayer, QgsField, QgsFeature, QgsMapLayer, QgsDataSourceUri
from qgis.utils import spatialite_connect

from .qgis_urlopener import remote_open_from_qgis
from .xml_utils import no_prefix, split_tag, resolve_xpath, xml_parse
from .gml_utils import extract_features

__all__ = ['load_as_xml_layer', 'properties_from_layer', 'is_layer_gml_xml']

def load_as_xml_layer(xml_uri, is_remote, attributes = {}, geometry_mapping = None, output_local_file = None, logger = None):
    """
    Load a GML file in a new QGIS layer
    :param xml_uri: the XML URI
    :param is_remote: True if it has to be fetched by http
    :param attributes: { 'attr1' : ( '//xpath/expression', QVariant.Int ) }
    :param geometry_mapping: XPath expression to a gml geometry node
    :returns: the created layer
    """
    if not output_local_file:
        import tempfile
        f = tempfile.NamedTemporaryFile()
        output_local_file = f.name
        f.close()

    #s = ComplexFeatureLoaderInSpatialite(output_local_file)
    s = ComplexFeatureLoaderInMemory()
    return s.load_complex_gml(xml_uri, is_remote, attributes, geometry_mapping, logger)

def properties_from_layer(layer):
    """Returns a tuple of metadata from the layer if it is a "GML as XML" layer"""
    return ComplexFeatureLoaderInMemory.properties_from_layer(layer)

def is_layer_gml_xml(layer):
    """Returns true if the input layer is a "GML as XML" layer"""
    return ComplexFeatureLoaderInMemory.is_layer_complex(layer)


#
# Implementation
#

def _wkbFromGml(tree):
    # extract the srid
    srid = 4326
    for k, v in tree.attrib.items():
        if no_prefix(k) == 'srsName':
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
    s = ET.tostring(tree, encoding="unicode")
    g = ogr.CreateGeometryFromGML(s)
    if g is None:
        return None
    return (g.ExportToWkb(), srid)

def _extractGmlGeometry(tree):
    ns, tag = split_tag(tree.tag)
    if ns.startswith('http://www.opengis.net/gml'):
        if tag in ["Point", "LineString", "Polygon",
                   "MultiPoint", "MultiCurve", "MultiSurface",
                   "Curve", "OrientableCurve", "Surface", 
                   "CompositeCurve", "CompositeSurface", "MultiGeometry"]:
            return _wkbFromGml(tree)
        
    for child in tree:
        g = _extractGmlGeometry(child)
        if g is not None:
            return g
    return None

def _extractGmlFromXPath(tree, xpath):
    #r = tree.xpath("./" + xpath, namespaces = tree.nsmap)
    r = resolve_xpath(tree, xpath)
    if len(r) > 0:
        return _wkbFromGml(r[0])
    return None

class ComplexFeatureSource(object):
    def __init__(self, xml, xpath_mapping = {}, geometry_mapping = None, logger = None):
        """
        Construct a ComplexFeatureSource

        :param xml: The input XML, as file io
        :param xpath_mapping: A mapping of XPath expressions to attributes. Example: { 'attribute' : ('//xpath/expression', QVariant.Int) }
        :param geometry_mapping: An XPath expression used to extract the geometry
        :param logger: a logger function
        """
        doc, _ = xml_parse(xml)
        self.features = extract_features(doc)
        self.title = no_prefix(self.features[0].tag)

        self.xpath_mapping = xpath_mapping
        self.geometry_mapping = geometry_mapping
        self.logger = logger

    def getFeatures(self):
        """
        The iterator that will yield a new feature.
        The yielded value is (feature_id, QgsGeometry or None, xml_tree: Element, { 'attr1' : value, 'attr2' : 'value' })
        """
        i = 1
        for feature in self.features:
            if self.logger is not None:
                self.logger.set_text("Feature {}/{}".format(i, len(self.features)))
                self.logger.set_progress(i, len(self.features))
                
            # get the id from gml:identifier, then from the "id" attribute
            fid = None
            for child in feature:
                f_ns, f_tag = split_tag(child.tag)
                if f_tag == 'identifier':
                    fid = child.text
                    break
            if fid is None:
                for k, v in feature.attrib.items():
                    f_ns, f_tag = split_tag(k)                    
                    if f_tag == "id":
                        fid = v
                        break
            if fid is None:
                fid = str(i)

            # get the geometry
            if self.geometry_mapping:
                wkb = _extractGmlFromXPath(feature, self.geometry_mapping)
            else:
                wkb = _extractGmlGeometry(feature)

            # get attribute values
            attrvalues = {}
            for attr, xpath_t in self.xpath_mapping.items():
                xpath, type = xpath_t
                # resolve xpath
                #r = feature.xpath("./" + xpath, namespaces = feature.nsmap)
                r = resolve_xpath(feature, xpath)
                v = None
                value = None
                if isinstance(r, str):
                    v = r
                if isinstance(r, str):
                    v = str(r)
                elif isinstance(r, ET.Element):
                    v = r.text
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
                        elif type == QVariant.DateTime:
                            value = v
                        else:
                            value = None
                    except ValueError:
                        value = None
                attrvalues[attr] = value

            yield i, fid, wkb, feature, attrvalues
            i += 1


class ComplexFeatureLoader(object):
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

    def load_complex_gml(self, xml_uri, is_remote, attributes = {}, geometry_mapping = None, logger = None):
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
        src = ComplexFeatureSource(xml, attributes, geometry_mapping, logger)

        layer = None
        attr_list = [ (k, v[1]) for k, v in attributes.items() ]
        for id, fid, g, xml, attrs in src.getFeatures():
            qgsgeom = None
            if g is None:
                if layer is None:
                    layer = self._create_layer('none', None, attr_list, src.title)
            else:
                wkb, srid = g
                qgsgeom = QgsGeometry()
                qgsgeom.fromWkb(wkb)
                if qgsgeom and qgsgeom.type() == QgsWkbTypes.PointGeometry:
                    if layer is None:
                        layer = self._create_layer('point', srid, attr_list, src.title + " (points)")
                elif qgsgeom and qgsgeom.type() == QgsWkbTypes.LineGeometry:
                    if layer is None:
                        layer = self._create_layer('linestring', srid, attr_list, src.title + " (lines)")
                elif qgsgeom and qgsgeom.type() == QgsWkbTypes.PolygonGeometry:
                    if layer is None:
                        layer = self._create_layer('polygon', srid, attr_list, src.title + " (polygons)")

            if layer is not None:
                self._add_properties_to_layer(layer, xml_uri, is_remote, attributes, geometry_mapping)

                pr = layer.dataProvider()
                f = QgsFeature(pr.fields(), id)
                if qgsgeom:
                    f.setGeometry(qgsgeom)
                f.setAttribute("id", str(id))
                f.setAttribute("fid", fid)
                f.setAttribute("_xml_", ET.tostring(xml).decode('utf8'))
                for k, v in attrs.items():
                    r = f.setAttribute(k, v)
                pr.addFeatures([f])

        return layer

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
        :param attributes: list of (attribute_name, attribute_type, attribute_typename)
        :param title: title of the layer
        """
        conn = spatialite_connect(self.output_local_file)
        cur = conn.cursor()
        cur.execute("SELECT InitSpatialMetadata(1)")
        cur.execute("DROP TABLE IF EXISTS meta")
        cur.execute("DROP TABLE IF EXISTS data")
        cur.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        cur.execute("CREATE TABLE data (id INT NOT NULL PRIMARY KEY, fid TEXT NOT NULL, _xml_ TEXT)")
        if srid:
            cur.execute("SELECT AddGeometryColumn('data', 'geometry', {}, '{}', 'XY')".format(srid, type))
        conn.close()

        if srid:
            layer = QgsVectorLayer("dbname='{}' table=\"data\" (geometry) sql=".format(self.output_local_file), title, "spatialite")
        else:
            layer = QgsVectorLayer("dbname='{}' table=\"data\" sql=".format(self.output_local_file), title, "spatialite")

        pr = layer.dataProvider()
        pr.addAttributes([QgsField("fid", QVariant.String)])
        pr.addAttributes([QgsField("_xml_", QVariant.String)])
        for aname, atype in attributes:
            atype_name = QVariant.typeToName(atype)
            pr.addAttributes([QgsField(aname, atype, atype_name)])
        layer.updateFields()
        return layer

    def _add_properties_to_layer(self, layer, xml_uri, is_remote, attributes, geom_mapping):
        import json
        conn = spatialite_connect(self.output_local_file)
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
        u = QgsDataSourceUri(layer.source())
        conn = spatialite_connect(u.database())
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
        u = QgsDataSourceUri(layer.source())
        try:
            conn = sqlite3.dbapi2.connect(u.database())
            cur = conn.cursor()
            cur.execute("SELECT value FROM meta WHERE key='complex_features'")
            for r in cur:
                return r[0] == '1'
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                return False
            raise
        return False

class ComplexFeatureLoaderInMemory(ComplexFeatureLoader):

    def _create_layer(self, geometry_type, srid, attributes, title):
        """
        Creates an empty memory layer
        :param geometry_type: 'Point', 'LineString', 'Polygon', etc.
        :param srid: CRS ID of the layer
        :param attributes: list of (attribute_name, attribute_type)
        :param title: title of the layer
        """
        if srid:
            layer = QgsVectorLayer("{}?crs=EPSG:{}&field=id:string".format(geometry_type, srid), title, "memory")
        else:
            layer = QgsVectorLayer("none?field=id:string", title, "memory")
        pr = layer.dataProvider()
        pr.addAttributes([QgsField("fid", QVariant.String)])
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


if __name__ == '__main__':
    # fix_print_with_import
    print("GSML4")
    src = ComplexFeatureSource( "../samples/GSML4-Borehole.xml", geometry_mapping = "/gsmlbh:location/gml:Point")
    for x in src.getFeatures():
        # fix_print_with_import
        print(x)
        
    print("mineral")
    src = ComplexFeatureSource( "../samples/mineral.xml")
    for x in src.getFeatures():
        # fix_print_with_import
        print(x)

    print("Boreholeview")
    src = ComplexFeatureSource( "../samples/BoreholeView.xml")
    for x in src.getFeatures():
        # fix_print_with_import
        print(x)

    print("airquality")
    src = ComplexFeatureSource( "../samples/airquality.xml", { 'mainEmissionSources' : ('.//aqd:mainEmissionSources/@xlink:href', QVariant.String),
                                                               'stationClassification' : ('.//aqd:stationClassification/@xlink:href', QVariant.String) })
    for x in src.getFeatures():
        # fix_print_with_import
        print(x)

    print("env_monitoring")
    src = ComplexFeatureSource( "../samples/env_monitoring.xml")
    for x in src.getFeatures():
        # fix_print_with_import
        print(x)

    print("env_monitoring1")
    src = ComplexFeatureSource( "../samples/env_monitoring1.xml")
    for x in src.getFeatures():
        # fix_print_with_import
        print(x)

