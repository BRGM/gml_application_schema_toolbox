#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

import os
import re
os.environ["XML_CATALOG_FILES"]="file:///home/hme/src/brgm_gml/scripts/catalog.xml"

from lxml import etree

from osgeo import ogr


def noPrefix(tag):
    if tag.startswith('{'):
        return tag[tag.rfind('}')+1:]
    return tag

def qgsGeometryFromGml(tree):
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
    qgs = QgsGeometry()
    qgs.fromWkb(g.ExportToWkb())
    return (qgs, srid)

def extractGmlGeometry(tree):
    if tree.prefix == "gml" and noPrefix(tree.tag) == "Point":
        return qgsGeometryFromGml(tree)
    for child in tree:
        g = extractGmlGeometry(child)
        if g is not None:
            return g
    return None

class ComplexFeatureSource:
    def __init__(self, xml_file):
        doc = etree.parse(open(xml_file))
        self.root = doc.getroot()
        if self.root.nsmap[self.root.prefix] != "http://www.opengis.net/wfs/2.0":
            raise RuntimeError("only wfs 2 streams are supported for now")

    def getFeatures(self):
        for child in self.root:
            fid = None
            for k, v in child[0].attrib.iteritems():
                if noPrefix(k) == "id":
                    fid = v
            geom = extractGmlGeometry(child[0])
            yield fid, geom, child[0]

class MyResolver(etree.Resolver):
    def resolve(self, url, id, context):
        print url
        return etree.Resolver.resolve( self, url, id, context )

class MainPlugin:

    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        self.action = QAction(QIcon("icon.png"), \
                              u"Load Complex Features", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"Complex Features", self.action)
    
    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu(u"Complex Features",self.action)


    def load_xml(self, xml_file, schema_file):
        if False:
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

        src = ComplexFeatureSource(xml_file)

        self.pointLayer = None
        for fid, g, xml in src.getFeatures():
            geom = None
            qgsgeom, srid = g
            if qgsgeom and qgsgeom.type() == QGis.Point:
                self.addToPointLayer(fid, qgsgeom, srid, xml)

    def addToPointLayer(self, fid, geom, srid, xml):
        if self.pointLayer is None:
            self.pointLayer = QgsVectorLayer("Point?crs=epsg:{}&field=id:string".format(srid), "points", "memory")
            pr = self.pointLayer.dataProvider()
            pr.addAttributes([QgsField("_tree_", QVariant.String)])
            self.pointLayer.updateFields()
            QgsMapLayerRegistry.instance().addMapLayer(self.pointLayer)
        pr = self.pointLayer.dataProvider()
        f = QgsFeature()
        f.setGeometry(geom)
        f.setAttributes([fid, etree.tostring(xml)])
        pr.addFeatures([f])

    def run(self):
        #xml_file = QFileDialog.getOpenFileName (None, "Select XML File", "/home/hme/src/brgm_xml", "*.xml;;*.gml")
        #if not xml_file:
        #    return

        #self.load_xml(xml_file, "")
        self.load_xml("/home/hme/src/brgm_gml/samples/env_monitoring.xml", "")

        #schema_file = QFileDialog.getOpenFileName (None, "Select Schema File", "/home/hme/src/brgm_xml", "*.xsd")
        #if not schema_file:
        #    return
