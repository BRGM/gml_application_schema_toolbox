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

# standard library
import copy
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from builtins import object, str

from osgeo import ogr, osr
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsMapLayer,
    QgsPointXY,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

from gml_application_schema_toolbox.core.gml_utils import extract_features
from gml_application_schema_toolbox.core.qgis_urlopener import remote_open_from_qgis
from gml_application_schema_toolbox.core.xml_utils import (
    no_prefix,
    remove_prefix,
    resolve_xpath,
    split_tag,
    xml_parse,
)

__all__ = ["load_as_xml_layer", "properties_from_layer", "is_layer_gml_xml"]


def load_as_xml_layer(
    xml_uri: str,
    is_remote: bool,
    attributes={},
    geometry_mapping=None,
    output_local_file=None,
    logger=None,
    swap_xy=False,
):
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
        f = tempfile.NamedTemporaryFile()
        output_local_file = f.name
        f.close()

    s = ComplexFeatureLoaderInGpkg(output_local_file)
    return s.load_complex_gml(
        xml_uri, is_remote, attributes, geometry_mapping, logger, swap_xy
    )


def properties_from_layer(layer):
    """Returns a tuple of metadata from the layer if it is a "GML as XML" layer"""
    return ComplexFeatureLoaderInMemory.properties_from_layer(layer)


def is_layer_gml_xml(layer):
    """Returns true if the input layer is a "GML as XML" layer"""
    return ComplexFeatureLoaderInMemory.is_layer_complex(layer)


#
# Implementation
#


def _swap_qgs_geometry(qgsgeom):
    if qgsgeom.wkbType() == QgsWkbTypes.Point:
        p = qgsgeom.asPoint()
        qgsgeom = QgsGeometry.fromPointXY(QgsPointXY(p[1], p[0]))
    elif qgsgeom.wkbType() == QgsWkbTypes.MultiPoint:
        mp = qgsgeom.asMultiPoint()
        qgsgeom = QgsGeometry.fromMultiPointXY([QgsPointXY(p[1], p[0]) for p in mp])
    elif qgsgeom.wkbType() == QgsWkbTypes.LineString:
        pl = qgsgeom.asPolyline()
        qgsgeom = QgsGeometry.fromPolylineXY([QgsPointXY(p[1], p[0]) for p in pl])
    elif qgsgeom.wkbType() == QgsWkbTypes.MultiLineString:
        mls = qgsgeom.asMultiPolyline()
        qgsgeom = QgsGeometry.fromMultiPolylineXY(
            [[QgsPointXY(p[1], p[0]) for p in pl] for pl in mls]
        )
    elif qgsgeom.wkbType() == QgsWkbTypes.Polygon:
        pl = qgsgeom.asPolygon()
        qgsgeom = QgsGeometry.fromPolygonXY(
            [[QgsPointXY(p[1], p[0]) for p in r] for r in pl]
        )
    elif qgsgeom.wkbType() == QgsWkbTypes.MultiPolygon:
        mp = qgsgeom.asMultiPolygon()
        qgsgeom = QgsGeometry.fromMultiPolygonXY(
            [[[QgsPointXY(p[1], p[0]) for p in r] for r in pl] for pl in mp]
        )
    return qgsgeom


def _get_srs_name(tree):
    # get srsName, either from the current element, or from a child
    for k, v in tree.attrib.items():
        if no_prefix(k) == "srsName":
            return v
    for child in tree:
        n = _get_srs_name(child)
        if n is not None:
            return n
    return None


def _get_srid_from_name(srs_name: str) -> tuple:
    """[summary]

    For reference:
        EPSG:4326
        urn:EPSG:geographicCRS:4326
        urn:ogc:def:crs:EPSG:4326
        urn:ogc:def:crs:EPSG::4326
        urn:ogc:def:crs:EPSG:6.6:4326
        urn:x-ogc:def:crs:EPSG:6.6:4326
        http://www.opengis.net/gml/srs/epsg.xml#4326
        http://www.epsg.org/6.11.2/4326

    :param srs_name: [description]
    :type srs_name: [str]
    :return: [description]
    :rtype: [type]
    """
    sr = osr.SpatialReference()

    # get the last number
    m = re.search("([0-9]+)/?$", srs_name)
    srid = int(m.group(1))
    sr.ImportFromEPSGA(srid)
    srid_axis_swapped = sr.EPSGTreatsAsLatLong() or sr.EPSGTreatsAsNorthingEasting()
    return (srid, srid_axis_swapped)


def _wkbFromGml(tree, swap_xy, default_srs=None):
    # extract the srid
    srid = None
    srid_axis_swapped = False

    srs_name = _get_srs_name(tree)
    if srs_name is None and default_srs is not None:
        srid, srid_axis_swapped = _get_srid_from_name(default_srs)
    elif srs_name is not None:
        srid, srid_axis_swapped = _get_srid_from_name(srs_name)
    else:
        # No SRID found, force to 4326
        srid, srid_axis_swapped = 4326, True

    # inversion
    swap_xy = swap_xy ^ srid_axis_swapped

    # call ogr for GML parsing
    s = ET.tostring(tree, encoding="unicode")
    g = ogr.CreateGeometryFromGML(s)
    if g is None:
        return None

    wkb = g.ExportToWkb()
    if g.GetGeometryType() in (ogr.wkbPolyhedralSurface, ogr.wkbTIN):
        # Polyhedral and TIN are not supported by QGIS
        # So we convert them to multipolygon by poking the geometry type
        # It works only because the memory structure is the same
        wkb = wkb[:4] + b"\x06" + wkb[5:]

    qgsgeom = QgsGeometry()
    qgsgeom.fromWkb(wkb)

    if swap_xy:
        qgsgeom = _swap_qgs_geometry(qgsgeom)
    return qgsgeom, srid


def _extractGmlGeometries(tree, swap_xy, default_srs=None, parent=None):
    geoms = []
    ns, tag = split_tag(tree.tag)
    if ns.startswith("http://www.opengis.net/gml"):
        if tag in [
            "Point",
            "LineString",
            "Polygon",
            "PolyhedralSurface",
            "Tin",
            "MultiPoint",
            "MultiLineString",
            "MultiPolygon",
            "MultiCurve",
            "MultiSurface",
            "Curve",
            "OrientableCurve",
            "Surface",
            "CompositeCurve",
            "CompositeSurface",
            "MultiGeometry",
            "Envelope",
        ]:
            g = _wkbFromGml(tree, swap_xy, default_srs)
            if g is not None:
                return [(g, parent.tag)]

    for child in tree:
        geoms += _extractGmlGeometries(child, swap_xy, default_srs, tree)
    return geoms


def _extractGmlFromXPath(tree, xpath, swap_xy, default_srs=None):
    r = resolve_xpath(tree, xpath)
    if r is not None:
        if isinstance(r, list):
            return [(_wkbFromGml(x, swap_xy, default_srs), "") for x in r]
        else:
            return [(_wkbFromGml(r, swap_xy, default_srs), "")]
    return None


class ComplexFeatureSource(object):
    def __init__(self, xml, xpath_mapping={}, geometry_mapping=None, logger=None):
        """
        Construct a ComplexFeatureSource

        :param xml: The input XML, as file io
        :param xpath_mapping: A mapping of XPath expressions to attributes. \
            Example: { 'attribute' : ('//xpath/expression', QVariant.Int) }
        :param geometry_mapping: An XPath expression used to extract the geometry
        :param logger: a logger function
        """
        doc, _ = xml_parse(xml)
        self.bbox, self.bbox_srs, self.features = extract_features(doc)
        if self.features:
            self.title = no_prefix(self.features[0].tag)
        else:
            self.title = ""
        self.xpath_mapping = xpath_mapping
        self.geometry_mapping = geometry_mapping
        self.logger = logger

    def getFeatures(self, swap_xy: bool = False):
        """
        The iterator that will yield a new feature.
        The yielded value is \
            (feature_id, QgsGeometry or None, xml_tree: Element, {
                'attr1' : value,
                'attr2' : 'value' }
            )

        @param swap_xy whether to force X/Y coordinate swapping
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
                if f_tag == "identifier":
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
                qgs_geoms = _extractGmlFromXPath(
                    feature, self.geometry_mapping, swap_xy, default_srs=self.bbox_srs
                )
            else:
                qgs_geoms = _extractGmlGeometries(
                    feature, swap_xy, default_srs=self.bbox_srs
                )

            # get attribute values
            attrvalues = {}
            feature2 = copy.deepcopy(feature)
            remove_prefix(feature2)
            for attr, xpath_t in self.xpath_mapping.items():
                xpath, value_type = xpath_t
                # resolve xpath
                r = resolve_xpath(feature2, xpath)
                v = None
                value = None
                if isinstance(r, str):
                    v = r
                elif isinstance(r, list):
                    v = "[" + ";".join([n.text for n in r]) + "]"
                elif isinstance(r, ET.Element):
                    v = r.text
                else:
                    v = None
                    value = None
                if v is not None:
                    try:
                        if value_type == QVariant.Int:
                            value = int(v)
                        elif value_type == QVariant.String:
                            value = v
                        elif value_type == QVariant.Double:
                            value = float(v)
                        elif value_type == QVariant.DateTime:
                            value = v
                        else:
                            value = None
                    except ValueError:
                        value = None
                attrvalues[attr] = value

            yield i, fid, qgs_geoms, feature, attrvalues
            i += 1


class ComplexFeatureLoader(object):
    """Allows to load a complex feature source and put features in a QGIS layer"""

    def _create_layer(self, geometry_type, srid, attributes, title, tag):
        raise RuntimeError("No default implementation, use a derived class")

    def _add_properties_to_layer(
        self, layer, xml_uri, is_remote, attributes, geom_mapping
    ):
        raise RuntimeError("No default implementation, use a derived class")

    @staticmethod
    def properties_from_layer(layer):
        raise RuntimeError("No default implementation, use a derived class")

    @staticmethod
    def is_layer_complex(layer):
        raise RuntimeError("No default implementation, use a derived class")

    def load_complex_gml(
        self,
        xml_uri: str,
        is_remote: bool,
        attributes={},
        geometry_mapping=None,
        logger=None,
        swap_xy: bool = False,
    ) -> dict:
        """
        :param xml_uri: the XML URI
        :param is_remote: True if it has to be fetched by http
        :param attributes: { 'attr1' : ( '//xpath/expression', QVariant.Int ) }
        :param geometry_mapping: XPath expression to a gml geometry node
        :param swap_xy: True if X/Y coordinates must be swapped
        :returns: the created layer
        """
        try:
            if is_remote:
                xml_src = remote_open_from_qgis(xml_uri)
            else:
                # Open the file in binary mode, this means returning bytes
                # instead of a string whose encoding would have to be interpreted
                # it is up to the XML parser to determine which encoding it is
                xml_src = open(xml_uri, "rb")

            src = ComplexFeatureSource(xml_src, attributes, geometry_mapping, logger)

            attr_list = [(k, v[1]) for k, v in attributes.items()]

            layers = {}
            features = {}
            for feat_id, fid, qgsgeoms, xml, attrs in src.getFeatures(swap_xy):
                # layer creation
                if qgsgeoms == []:
                    if "" not in layers:
                        layer = self._create_layer(
                            "none", None, attr_list, src.title, "nogeom"
                        )

                        self._add_properties_to_layer(
                            layer, xml_uri, is_remote, attributes, geometry_mapping
                        )
                        layers["nogeom"] = layer
                else:
                    for (qgsgeom, srid), tag in qgsgeoms:
                        if tag in layers:
                            continue
                        type2d = QgsWkbTypes.flatType(qgsgeom.wkbType())
                        typemap = {
                            QgsWkbTypes.Point: "point",
                            QgsWkbTypes.MultiPoint: "multipoint",
                            QgsWkbTypes.LineString: "linestring",
                            QgsWkbTypes.MultiLineString: "multilinestring",
                            QgsWkbTypes.Polygon: "polygon",
                            QgsWkbTypes.MultiPolygon: "multipolygon",
                            QgsWkbTypes.CompoundCurve: "compoundcurve",
                            QgsWkbTypes.CircularString: "compoundcurve",
                            QgsWkbTypes.MultiCurve: "multicurve",
                            QgsWkbTypes.CurvePolygon: "curvepolygon",
                            QgsWkbTypes.MultiSurface: "multisurface",
                        }
                        if qgsgeom and type2d in typemap:
                            title = "{} ({})".format(src.title, no_prefix(tag))
                            layer = self._create_layer(
                                typemap[QgsWkbTypes.multiType(type2d)],
                                srid,
                                attr_list,
                                title,
                                no_prefix(tag),
                            )
                        else:
                            raise RuntimeError(
                                "Unsupported geometry type {}".format(qgsgeom.wkbType())
                            )
                        self._add_properties_to_layer(
                            layer, xml_uri, is_remote, attributes, geometry_mapping
                        )
                        layers[tag] = layer

                # collect features
                f = QgsFeature(layer.dataProvider().fields(), feat_id)
                f.setAttribute("id", str(feat_id))
                f.setAttribute("fid", fid)
                for k, v in attrs.items():
                    f.setAttribute(k, v)
                for g, tag in qgsgeoms:
                    if tag not in features:
                        features[tag] = []
                    fcopy = QgsFeature(f)
                    fcopy.setAttribute("_xml_", ET.tostring(xml).decode("utf8"))
                    if g:
                        qgsgeom, _ = g
                        if QgsWkbTypes.isMultiType(
                            layers[tag].wkbType()
                        ) and QgsWkbTypes.isSingleType(qgsgeom.wkbType()):
                            # force multi
                            qgsgeom.convertToMultiType()
                        fcopy.setGeometry(qgsgeom)
                    features[tag].append(fcopy)

            # write features
            for tag, f in features.items():
                if len(f) > 0:
                    layer = layers[tag]
                    layer.startEditing()
                    layer.addFeatures(f)
                    layer.commitChanges()
        finally:
            xml_src.close()

        # Set the styl for polygons coming from boundedBy
        for tag_name, layer in layers.items():
            if tag_name.endswith("boundedBy"):
                layer.loadNamedStyle(
                    os.path.join(
                        os.path.dirname(__file__), "..", "gui", "bounded_by_style.qml"
                    )
                )
        return layers


class ComplexFeatureLoaderInMemory(ComplexFeatureLoader):
    def _create_layer(self, geometry_type, srid, attributes, title, tag):
        """
        Creates an empty memory layer
        :param geometry_type: 'Point', 'LineString', 'Polygon', etc.
        :param srid: CRS ID of the layer
        :param attributes: list of (attribute_name, attribute_type)
        :param title: title of the layer
        """
        if srid:
            layer = QgsVectorLayer(
                "{}?crs=EPSG:{}&field=id:string".format(geometry_type, srid),
                title,
                "memory",
            )
        else:
            layer = QgsVectorLayer("none?field=id:string", title, "memory")
        pr = layer.dataProvider()
        pr.addAttributes([QgsField("fid", QVariant.String)])
        pr.addAttributes([QgsField("_xml_", QVariant.String)])
        for aname, atype in attributes:
            pr.addAttributes([QgsField(aname, atype)])
        layer.updateFields()
        return layer

    def _add_properties_to_layer(
        self, layer, xml_uri, is_remote, attributes, geom_mapping
    ):
        layer.setCustomProperty("complex_features", True)
        layer.setCustomProperty("xml_uri", xml_uri)
        layer.setCustomProperty("is_remote", is_remote)
        layer.setCustomProperty("attributes", attributes)
        layer.setCustomProperty("geom_mapping", geom_mapping)

    @staticmethod
    def properties_from_layer(layer):
        return (
            layer.customProperty("complex_features", False),
            layer.customProperty("xml_uri", ""),
            layer.customProperty("is_remote", False),
            layer.customProperty("attributes", {}),
            layer.customProperty("geom_mapping", None),
            None,  # output filename
        )

    @staticmethod
    def is_layer_complex(layer):
        return layer.type() == QgsMapLayer.VectorLayer and layer.customProperty(
            "complex_features", False
        )


class ComplexFeatureLoaderInGpkg(ComplexFeatureLoader):
    def __init__(self, output_local_file: str):
        """
        :param output_local_file: name of the local sqlite file
        """
        self.output_local_file = output_local_file

    def _create_layer(self, geom_type: str, srid, attributes, title, tag):
        """Creates an empty spatialite layer.

        :param geom_type: 'Point', 'LineString', 'Polygon', etc.
        :param srid: CRS ID of the layer
        :param attributes: list of (attribute_name, attribute_type, attribute_typename)
        :param title: title of the layer
        """
        driver = ogr.GetDriverByName("GPKG")
        fn = "{}_{}.gpkg".format(self.output_local_file, tag)
        ds = driver.CreateDataSource(fn)
        layer = ds.CreateLayer("meta", geom_type=ogr.wkbNone)
        layer.CreateField(ogr.FieldDefn("key", ogr.OFTString))
        layer.CreateField(ogr.FieldDefn("value", ogr.OFTString))

        if srid:
            wkbType = {
                "point": ogr.wkbPoint25D,
                "multipoint": ogr.wkbMultiPoint25D,
                "linestring": ogr.wkbLineString25D,
                "multilinestring": ogr.wkbMultiLineString25D,
                "polygon": ogr.wkbPolygon25D,
                "multipolygon": ogr.wkbMultiPolygon25D,
                "compoundcurve": ogr.wkbCompoundCurveZ,
                "curvepolygon": ogr.wkbCurvePolygonZ,
                "multicurve": ogr.wkbMultiCurveZ,
                "multisurface": ogr.wkbMultiSurfaceZ,
            }[geom_type]
            srs = osr.SpatialReference()
            srs.ImportFromEPSGA(int(srid))
        else:
            wkbType = ogr.wkbNone
            srs = None
        layer = ds.CreateLayer("data", srs, wkbType, ["FID=id"])
        layer.CreateField(ogr.FieldDefn("id", ogr.OFTInteger64))
        layer.CreateField(ogr.FieldDefn("fid", ogr.OFTString))
        layer.CreateField(ogr.FieldDefn("_xml_", ogr.OFTString))

        att_type_map = {
            QVariant.String: ogr.OFTString,
            QVariant.Int: ogr.OFTInteger,
            QVariant.Double: ogr.OFTReal,
            QVariant.DateTime: ogr.OFTDateTime,
        }
        for aname, atype in attributes:
            layer.CreateField(ogr.FieldDefn(aname, att_type_map[atype]))

        # update fields
        layer.ResetReading()

        del layer
        del ds

        qgs_layer = QgsVectorLayer("{}|layername=data".format(fn), title, "ogr")
        qgs_layer.setCustomProperty("tag", tag)
        return qgs_layer

    def _add_properties_to_layer(
        self, layer, xml_uri, is_remote, attributes, geom_mapping
    ):
        tag = layer.customProperty("tag")
        fn = "{}_{}.gpkg".format(self.output_local_file, tag)
        qgs_layer = QgsVectorLayer("{}|layername=meta".format(fn), "meta", "ogr")
        pr = qgs_layer.dataProvider()
        metas = (
            ("complex_features", "1"),
            ("xml_uri", xml_uri),
            ("is_remote", "1" if is_remote else "0"),
            ("attributes", json.dumps(attributes)),
            ("geom_mapping", json.dumps(geom_mapping)),
            ("output_filename", self.output_local_file),
        )
        features = []
        for k, v in metas:
            f = QgsFeature(pr.fields())
            f["key"] = k
            f["value"] = v
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
        tag = layer.customProperty("tag", None)
        if not tag:
            return nil
        pkg_file = layer.source()[: layer.source().find("|")]
        qgs_layer = QgsVectorLayer("{}|layername=meta".format(pkg_file), "meta", "ogr")
        ret = list(nil)
        for f in qgs_layer.getFeatures():
            if f["key"] == "complex_features":
                ret[0] = f["value"] == "1"
            elif f["key"] == "xml_uri":
                ret[1] = f["value"]
            elif f["key"] == "is_remote":
                ret[2] = f["value"] == "1"
            elif f["key"] == "attributes":
                ret[3] = json.loads(f["value"])
            elif f["key"] == "geom_mapping":
                ret[4] = json.loads(f["value"])
            elif f["key"] == "output_filename":
                ret[5] = f["value"]
        return ret

    @staticmethod
    def is_layer_complex(layer):
        if layer.type() != QgsMapLayer.VectorLayer:
            return False
        if layer.providerType() != "ogr":
            return False
        tag = layer.customProperty("tag", None)
        if not tag:
            return False
        pkg_file = layer.source()[: layer.source().find("|")]
        qgs_layer = QgsVectorLayer("{}|layername=meta".format(pkg_file), "meta", "ogr")
        if not qgs_layer.isValid():
            return False
        return [
            f["value"] == "1"
            for f in qgs_layer.getFeatures()
            if f["key"] == "complex_features"
        ][0]
