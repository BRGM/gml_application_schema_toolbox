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
from osgeo import ogr, osr
import re

from qgis.PyQt.QtCore import QVariant, QDateTime

from qgis.core import QgsWkbTypes, QgsGeometry, QgsVectorLayer, QgsField, QgsFeature, QgsMapLayer, QgsDataSourceUri, QgsPointXY

from .qgis_urlopener import remote_open_from_qgis
from .xml_utils import no_prefix, split_tag, resolve_xpath, xml_parse
from .gml_utils import extract_features

__all__ = ['load_as_xml_layer', 'properties_from_layer', 'is_layer_gml_xml']

def load_as_xml_layer(xml_uri, is_remote, attributes = {}, geometry_mapping = None, output_local_file = None, logger = None, swap_xy = False):
    """
    Load a GML file in a new QGIS layer
    :param xml_uri: the XML URI
    :param is_remote: True if it has to be fetched by http
    :param attributes: { 'attr1' : ( '//xpath/expression', QVariant.Int ) }
    :param geometry_mapping: XPath expression to a gml geometry node
    :param swap_xy: True to swap X/Y coordinates
    :returns: the created layer
    """
    if not output_local_file:
        import tempfile
        f = tempfile.NamedTemporaryFile()
        output_local_file = f.name
        f.close()

    s = ComplexFeatureLoaderInGpkg(output_local_file)
    return s.load_complex_gml(xml_uri, is_remote, attributes, geometry_mapping, logger, swap_xy)

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

    def load_complex_gml(self, xml_uri, is_remote, attributes = {}, geometry_mapping = None, logger = None, swap_xy = False):
        """
        :param xml_uri: the XML URI
        :param is_remote: True if it has to be fetched by http
        :param attributes: { 'attr1' : ( '//xpath/expression', QVariant.Int ) }
        :param geometry_mapping: XPath expression to a gml geometry node
        :param swap_xy: True if X/Y coordinates must be swapped
        :returns: the created layer
        """
        if is_remote:
            xml = remote_open_from_qgis(xml_uri)
        else:
            # Open the file in binary mode, this means returning bytes
            # instead of a string whose encoding would have to be interpreted
            # it is up to the XML parser to determine which encoding it is
            xml = open(xml_uri, 'rb')
        src = ComplexFeatureSource(xml, attributes, geometry_mapping, logger)

        attr_list = [ (k, v[1]) for k, v in attributes.items() ]
        
        # first feature
        id, fid, g, xml, attrs = next(src.getFeatures())
        qgsgeom = None
        if g is None:
            layer = self._create_layer('none', None, attr_list, src.title)
        else:
            wkb, srid = g
            qgsgeom = QgsGeometry()
            qgsgeom.fromWkb(wkb)
            if qgsgeom and qgsgeom.type() == QgsWkbTypes.PointGeometry:
                layer = self._create_layer('point', srid, attr_list, src.title + " (points)")
            elif qgsgeom and qgsgeom.type() == QgsWkbTypes.LineGeometry:
                layer = self._create_layer('linestring', srid, attr_list, src.title + " (lines)")
            elif qgsgeom and qgsgeom.type() == QgsWkbTypes.PolygonGeometry:
                layer = self._create_layer('polygon', srid, attr_list, src.title + " (polygons)")

        # add metadata
        self._add_properties_to_layer(layer, xml_uri, is_remote, attributes, geometry_mapping)

        # collect features
        features = []
        for id, fid, g, xml, attrs in src.getFeatures():
            qgsgeom = None
            wkb, srid = g
            qgsgeom = QgsGeometry()
            qgsgeom.fromWkb(wkb)
            if qgsgeom and qgsgeom.type() == QgsWkbTypes.PointGeometry:
                if swap_xy:
                    p = qgsgeom.asPoint()
                    qgsgeom = QgsGeometry.fromPoint(QgsPointXY(p[1], p[0]))
            elif qgsgeom and qgsgeom.type() == QgsWkbTypes.LineGeometry:
                if swap_xy:
                    pl = qgsgeom.asPolyline()
                    qgsgeom = QgsGeometry.fromPolyline([QgsPointXY(p[1],p[0]) for p in pl])
            elif qgsgeom and qgsgeom.type() == QgsWkbTypes.PolygonGeometry:
                if swap_xy:
                    pl = qgsgeom.asPolygon()
                    qgsgeom = QgsGeometry.fromPolygon([[QgsPointXY(p[1],p[0]) for p in r] for r in pl])

            f = QgsFeature(layer.dataProvider().fields(), id)
            if qgsgeom:
                f.setGeometry(qgsgeom)
            f.setAttribute("id", str(id))
            f.setAttribute("fid", fid)
            f.setAttribute("_xml_", ET.tostring(xml).decode('utf8'))
            for k, v in attrs.items():
                r = f.setAttribute(k, v)
            features.append(f)

        # write features
        if len(features) > 0:
            layer.dataProvider().addFeatures(features)

        return layer

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

class ComplexFeatureLoaderInGpkg(ComplexFeatureLoader):

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
        driver = ogr.GetDriverByName('GPKG')
        ds = driver.CreateDataSource(self.output_local_file)
        layer = ds.CreateLayer("meta", geom_type = ogr.wkbNone)
        layer.CreateField(ogr.FieldDefn('key', ogr.OFTString))
        layer.CreateField(ogr.FieldDefn('value', ogr.OFTString))

        if srid:
            wkbType = { 'point': ogr.wkbPoint,
                        'linestring': ogr.wkbLineString,
                        'polygon': ogr.wkbPolygon }[type]
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(int(srid))
        else:
            wkbType = ogr.wkbNone
            srs = None
        layer = ds.CreateLayer("data", srs, wkbType, ['FID=id'])
        layer.CreateField(ogr.FieldDefn('id', ogr.OFTInteger64))
        layer.CreateField(ogr.FieldDefn('fid', ogr.OFTString))
        layer.CreateField(ogr.FieldDefn('_xml_', ogr.OFTString))

        att_type_map = {QVariant.String : ogr.OFTString,
                        QVariant.Int : ogr.OFTInteger,
                        QVariant.Double: ogr.OFTReal,
                        QVariant.DateTime: ogr.OFTDateTime}
        for aname, atype in attributes:
            layer.CreateField(ogr.FieldDefn(aname, att_type_map[atype]))

        # update fields
        layer.ResetReading()

        qgs_layer = QgsVectorLayer("{}|layername=data".format(self.output_local_file), title, "ogr")
        return qgs_layer

    def _add_properties_to_layer(self, layer, xml_uri, is_remote, attributes, geom_mapping):
        import json
        qgs_layer = QgsVectorLayer("{}|layername=meta".format(self.output_local_file), "meta", "ogr")
        pr = qgs_layer.dataProvider()
        metas = (('complex_features','1'),
             ('xml_uri', xml_uri),
             ('is_remote', '1' if is_remote else '0'),
             ('attributes', json.dumps(attributes)),
             ('geom_mapping', json.dumps(geom_mapping)),
             ('output_filename', self.output_local_file))
        features=[]
        for k, v in metas:
            f = QgsFeature(pr.fields())
            f['key'] = k
            f['value'] = v
            features.append(f)
        pr.addFeatures(features)

    @staticmethod
    def properties_from_layer(layer):
        import json
        nil = (False, None, None, None, None, None)
        if layer.type() != QgsMapLayer.VectorLayer:
            return nil
        if layer.providerType() != "ogr":
            return nil
        if not layer.source().endswith('|layername=data'):
            return nil
        pkg_file = layer.source()[:layer.source().find('|')]
        qgs_layer = QgsVectorLayer("{}|layername=meta".format(pkg_file), "meta", "ogr")
        ret = list(nil)
        for f in qgs_layer.getFeatures():
            if f['key'] == 'complex_features':
                ret[0] = f['value'] == '1'
            elif f['key'] == 'xml_uri':
                ret[1] = f['value']
            elif f['key'] == 'is_remote':
                ret[2] = f['value'] == '1'
            elif f['key'] == 'attributes':
                ret[3] = json.loads(f['value'])
            elif f['key'] == 'geom_mapping':
                ret[4] = json.loads(f['value'])
            elif f['key'] == 'output_filename':
                ret[5] = f['value']
        return ret

    @staticmethod
    def is_layer_complex(layer):
        if layer.type() != QgsMapLayer.VectorLayer:
            return False
        if layer.providerType() != "ogr":
            return False
        if not layer.source().endswith('|layername=data'):
            return False
        pkg_file = layer.source()[:layer.source().find('|')]
        qgs_layer = QgsVectorLayer("{}|layername=meta".format(pkg_file), "meta", "ogr")
        if not qgs_layer.isValid():
            return False
        return [f['value'] == '1' for f in qgs_layer.getFeatures() if f['key'] == 'complex_features'][0]
