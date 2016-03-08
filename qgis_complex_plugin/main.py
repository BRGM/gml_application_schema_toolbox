#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtXml import *
from qgis.core import *
from qgis.gui import *

import os
#os.environ["XML_CATALOG_FILES"]="file:///home/hme/src/brgm_gml/scripts/catalog.xml"

from complex_features import ComplexFeatureSource, noPrefix
from identify_dialog import IdentifyDialog
from creation_dialog import CreationDialog

from lxml import etree

from xml_tree_widget import XMLTreeWidget

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

def createMemoryLayer(type, srid, attributes, title):
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

    # add init code
    layer.editFormConfig().setInitCode(u'import complex_features\nimport complex_features.main\nfrom complex_features.main import on_qgis_form_open')
    layer.editFormConfig().setInitCodeSource(QgsEditFormConfig.CodeSourceDialog)
    layer.editFormConfig().setInitFunction("on_qgis_form_open")
    return layer

def addPropertiesToLayer(layer, xml_uri, is_remote, attributes):
    layer.setCustomProperty("complex_features", True)
    layer.setCustomProperty("xml_uri", xml_uri)
    layer.setCustomProperty("is_remote", is_remote)
    layer.setCustomProperty("attributes", attributes)

def propertiesFromLayer(layer):
    return (layer.customProperty("complex_features", False),
            layer.customProperty("xml_uri", ""),
            layer.customProperty("is_remote", False),
            layer.customProperty("attributes", {}))

def replace_layer(old_layer, new_layer):
    """Convenience function to replace a layer in the legend"""
    # Add to the registry, but not to the legend
    QgsMapLayerRegistry.instance().addMapLayer(new_layer, False)
    # Copy symbology
    dom = QDomImplementation()
    doc = QDomDocument(dom.createDocumentType("qgis", "http://mrcc.com/qgis.dtd", "SYSTEM"))
    root_node = doc.createElement("qgis")
    root_node.setAttribute("version", "%s" % QGis.QGIS_VERSION)
    doc.appendChild(root_node)
    error = ""
    old_layer.writeSymbology(root_node, doc, error)
    new_layer.readSymbology(root_node, error)
    # insert the new layer above the old one
    root = QgsProject.instance().layerTreeRoot()
    in_tree = root.findLayer(old_layer.id())
    idx = 0
    for vl in in_tree.parent().children():
        if vl.layer() == old_layer:
            break
        idx += 1
    parent = in_tree.parent() if in_tree.parent() else root
    parent.insertLayer(idx, new_layer)
    QgsMapLayerRegistry.instance().removeMapLayer(old_layer)


class MyResolver(etree.Resolver):
    def resolve(self, url, id, context):
        print url
        return etree.Resolver.resolve( self, url, id, context )

class MainPlugin:

    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        self.action = QAction(QIcon(os.path.dirname(__file__) + "/mActionAddGMLLayer.svg"), \
                              u"Add/Edit Complex Features Layer", self.iface.mainWindow())
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
        :returns: the created layer
        """
        if is_remote:
            xml_file, _ = urllib.urlretrieve(xml_uri)
        else:
            xml_file = xml_uri
        src = ComplexFeatureSource(xml_file, attributes)

        self.layer = None
        for fid, g, xml, attrs in src.getFeatures():
            qgsgeom = None
            if g is None:
                if self.layer is None:
                    self.layer = createMemoryLayer('none', None, [ (k, v[1]) for k, v in attributes.iteritems() ], src.title)
            else:
                wkb, srid = g
                qgsgeom = QgsGeometry()
                qgsgeom.fromWkb(wkb)
                if qgsgeom and qgsgeom.type() == QGis.Point:
                    if self.layer is None:
                        self.layer = createMemoryLayer('point', srid, [ (k, v[1]) for k, v in attributes.iteritems() ], src.title + " (points)")
                elif qgsgeom and qgsgeom.type() == QGis.Line:
                    if self.layer is None:
                        self.layer = createMemoryLayer('linestring', srid, [ (k, v[1]) for k, v in attributes.iteritems() ], src.title + " (lines)")
                elif qgsgeom and qgsgeom.type() == QGis.Polygon:
                    if self.layer is None:
                        self.layer = createMemoryLayer('polygon', srid, [ (k, v[1]) for k, v in attributes.iteritems() ], src.title + " (polygons)")

            if self.layer:
                addPropertiesToLayer(self.layer, xml_uri, is_remote, attributes)

                pr = self.layer.dataProvider()
                f = QgsFeature(pr.fields())
                if qgsgeom:
                    f.setGeometry(qgsgeom)
                f.setAttribute("id", fid)
                f.setAttribute("_xml_", etree.tostring(xml))
                for k, v in attrs.iteritems():
                    r = f.setAttribute(k, v)
                pr.addFeatures([f])

        return self.layer

    def onAddLayer(self):
        layer_edited = False
        sel = self.iface.legendInterface().selectedLayers()
        if len(sel) > 0:
            sel_layer = sel[0]
        if sel:
            layer_edited, xml_uri, is_remote, attributes = propertiesFromLayer(sel_layer)

        if layer_edited:
            creation_dlg = CreationDialog(xml_uri, is_remote, attributes)
        else:
            creation_dlg = CreationDialog()
        r = creation_dlg.exec_()
        if r:
            is_remote, url = creation_dlg.source()
            mapping = creation_dlg.attribute_mapping()
            new_layer = self.load_xml(url, is_remote, mapping)

            if creation_dlg.replace_current_layer():
                replace_layer(sel_layer, new_layer)
            else:
                # a new layer
                QgsMapLayerRegistry.instance().addMapLayer(new_layer)

    def onIdentify(self):
        self.mapTool = IdentifyGeometry(self.iface.mapCanvas())
        self.mapTool.geomIdentified.connect(self.onGeometryIdentified)
        self.iface.mapCanvas().setMapTool(self.mapTool)

    def onGeometryIdentified(self, layer, feature):
        # disable map tool
        self.iface.mapCanvas().setMapTool(None)

        self.dlg = IdentifyDialog(layer, feature)
        self.dlg.exec_()
        

# Function to be called when a form on the complex feature layer is opened
def on_qgis_form_open(dialog, layer, feature):
    # look for the '_xml_' QLabel in the form dialog
    label = [o for o in dialog.findChildren(QLabel) if o.text() == '_xml_'][0]
    grid = label.parent().layout()
    w = None
    wi = 0
    # look for the associated widget (most probably a QLineEdit)
    for i in range(grid.rowCount()):
        if grid.itemAtPosition(i, 0).widget() == label:
            w = grid.itemAtPosition(i, 1).widget()
            wi = i
            break
    if w is None:
        return

    # replace the QLineEdit with a XMLTreeWidget
    nw = XMLTreeWidget(layer, feature, dialog)
    del w
    grid.addWidget(nw, wi, 1)
