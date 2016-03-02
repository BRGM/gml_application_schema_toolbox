#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

import os
os.environ["XML_CATALOG_FILES"]="file:///home/hme/src/brgm_gml/scripts/catalog.xml"

from complex_features import ComplexFeatureSource

from lxml import etree

def createMemoryLayer(type, srid, attributes):
    """
    Creates an empty memory layer
    :param type: 'Point', 'LineString', 'Polygon', etc.
    :param srid: CRS ID of the layer
    :param attributes: list of (attribute_name, attribute_type)
    """
    layer = QgsVectorLayer("{}?crs=epsg:{}&field=id:string".format(type, srid), "points", "memory")
    pr = layer.dataProvider()
    pr.addAttributes([QgsField("_xml_", QVariant.String)])
    for aname, atype in attributes:
        pr.addAttributes([QgsField(aname, atype)])
    layer.updateFields()
    QgsMapLayerRegistry.instance().addMapLayer(layer)
    return layer

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


    def load_xml(self, xml_file, schema_file, attributes = {}):
        """
        :param xml_file: the XML filename
        :param schema_file: the schema filename
        :param attributes: { 'attr1' : ( '//xpath/expression', QVariant.Int ) }
        """
        src = ComplexFeatureSource(xml_file, attributes)

        self.pointLayer = None
        for fid, g, xml, attrs in src.getFeatures():
            wkb, srid = g
            qgsgeom = QgsGeometry()
            qgsgeom.fromWkb(wkb)
            if qgsgeom and qgsgeom.type() == QGis.Point:
                if self.pointLayer is None:
                    self.pointLayer = createMemoryLayer('Point', srid, [ (k, v[1]) for k, v in attributes.iteritems() ])

                pr = self.pointLayer.dataProvider()
                f = QgsFeature(pr.fields())
                f.setGeometry(qgsgeom)
                f.setAttribute("id", fid)
                f.setAttribute("_xml_", etree.tostring(xml))
                for k, v in attrs.iteritems():
                    r = f.setAttribute(k, v)
                pr.addFeatures([f])

    def run(self):
        #xml_file = QFileDialog.getOpenFileName (None, "Select XML File", "/home/hme/src/brgm_xml", "*.xml;;*.gml")
        #if not xml_file:
        #    return

        #self.load_xml(xml_file, "")
        #self.load_xml("/home/hme/src/brgm_gml/samples/env_monitoring.xml", "", attributes = { 'inspireId' : ('.//ef:inspireId//base:localId', QVariant.String) })
        self.load_xml("/home/hme/src/brgm_gml/samples/airquality.xml", "", { 'mainEmissionSources' : ('.//aqd:mainEmissionSources/@xlink:href', QVariant.String),
                                                                             'stationClassification' : ('.//aqd:stationClassification/@xlink:href', QVariant.String) })

        #schema_file = QFileDialog.getOpenFileName (None, "Select Schema File", "/home/hme/src/brgm_xml", "*.xsd")
        #if not schema_file:
        #    return
