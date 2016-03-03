#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

import os
os.environ["XML_CATALOG_FILES"]="file:///home/hme/src/brgm_gml/scripts/catalog.xml"

from complex_features import ComplexFeatureSource, noPrefix
from identify_dialog import IdentifyDialog
from creation_dialog import CreationDialog

from lxml import etree

import urllib

class IdentifyGeometry(QgsMapToolIdentify):
    geomIdentified = pyqtSignal(QgsVectorLayer, QgsFeature)
    
    def __init__(self, canvas):
        self.canvas = canvas
        QgsMapToolIdentify.__init__(self, canvas)
 
    def canvasReleaseEvent(self, mouseEvent):
        results = self.identify(mouseEvent.x(), mouseEvent.y(), self.TopDownStopAtFirst, self.VectorLayer)
        if len(results) > 0:
            self.geomIdentified.emit(results[0].mLayer, results[0].mFeature)

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

def addPropertiesToLayer(layer, xml_uri, is_remote, attributes):
    layer.setCustomProperty("complex_features", True)
    layer.setCustomProperty("xml_uri", xml_uri)
    layer.setCustomProperty("is_remote", is_remote)
    layer.setCustomProperty("attributes", attributes)

class MyResolver(etree.Resolver):
    def resolve(self, url, id, context):
        print url
        return etree.Resolver.resolve( self, url, id, context )

class MainPlugin:

    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        self.action = QAction(QIcon(os.path.dirname(__file__) + "/mActionAddGMLLayer.svg"), \
                              u"Add Complex Features Layer", self.iface.mainWindow())
        self.action.triggered.connect(self.onAddLayer)
        self.identifyAction = QAction(QIcon(os.path.dirname(__file__) + "/mActionIdentifyGML.svg"), \
                              u"Identify GML feature", self.iface.mainWindow())
        self.identifyAction.triggered.connect(self.onIdentify)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"Complex Features", self.action)
        self.iface.addToolBarIcon(self.identifyAction)
        self.iface.addPluginToMenu(u"Complex Features", self.identifyAction)
    
    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu(u"Complex Features",self.action)
        self.iface.removeToolBarIcon(self.identifyAction)
        self.iface.removePluginMenu(u"Complex Features",self.identifyAction)


    def load_xml(self, xml_uri, is_remote, attributes = {}):
        """
        :param xml_uri: the XML URI
        :param is_remote: True if it has to be fetched by http
        :param attributes: { 'attr1' : ( '//xpath/expression', QVariant.Int ) }
        """
        if is_remote:
            xml_file, _ = urllib.urlretrieve(xml_uri)
        else:
            xml_file = xml_uri
        src = ComplexFeatureSource(xml_file, attributes)

        self.pointLayer = None
        for fid, g, xml, attrs in src.getFeatures():
            wkb, srid = g
            qgsgeom = QgsGeometry()
            qgsgeom.fromWkb(wkb)
            if qgsgeom and qgsgeom.type() == QGis.Point:
                if self.pointLayer is None:
                    self.pointLayer = createMemoryLayer('Point', srid, [ (k, v[1]) for k, v in attributes.iteritems() ])
                    addPropertiesToLayer(self.pointLayer, xml_uri, is_remote, attributes)

                pr = self.pointLayer.dataProvider()
                f = QgsFeature(pr.fields())
                f.setGeometry(qgsgeom)
                f.setAttribute("id", fid)
                f.setAttribute("_xml_", etree.tostring(xml))
                for k, v in attrs.iteritems():
                    r = f.setAttribute(k, v)
                pr.addFeatures([f])

    def onAddLayer(self):
        creation_dlg = CreationDialog()
        r = creation_dlg.exec_()
        if r:
            is_remote, url = creation_dlg.source()
            mapping = creation_dlg.attribute_mapping()
            self.load_xml(url, is_remote, mapping)
        #xml_file = QFileDialog.getOpenFileName (None, "Select XML File", "/home/hme/src/brgm_xml", "*.xml;;*.gml")
        #if not xml_file:
        #    return

        #self.load_xml(xml_file, "")
        #self.load_xml("/home/hme/src/brgm_gml/samples/env_monitoring.xml", "", { 'inspireId' : ('.//ef:inspireId//base:localId', QVariant.String) })
        #self.load_xml("/home/hme/src/brgm_gml/samples/airquality.xml", "", { 'mainEmissionSources' : ('.//aqd:mainEmissionSources/@xlink:href', QVariant.String),
        #                                                                     'stationClassification' : ('.//aqd:stationClassification/@xlink:href', QVariant.String) })

        #schema_file = QFileDialog.getOpenFileName (None, "Select Schema File", "/home/hme/src/brgm_xml", "*.xsd")
        #if not schema_file:
        #    return

    def onIdentify(self):
        self.mapTool = IdentifyGeometry(self.iface.mapCanvas())
        self.mapTool.geomIdentified.connect(self.onGeometryIdentified)
        self.iface.mapCanvas().setMapTool(self.mapTool)

    def onGeometryIdentified(self, layer, feature):
        # disable map tool
        self.iface.mapCanvas().setMapTool(None)

        self.dlg = IdentifyDialog(layer, feature)
        self.dlg.exec_()
        
        
