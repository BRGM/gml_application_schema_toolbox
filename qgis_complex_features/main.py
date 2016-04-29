#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtXml import *
from qgis.core import *
from qgis.gui import *

import os

import platform
package_path = [os.path.join(os.path.dirname(__file__), "whl", "all")]
if platform.architecture() == ('64bit', 'WindowsPE'):
    package_path.append(os.path.join(os.path.dirname(__file__), "whl", "win64"))
elif platform.architecture() == ('32bit', 'WindowsPE'):
    package_path.append(os.path.join(os.path.dirname(__file__), "whl", "win32"))
import sys
if not set(package_path).issubset(set(sys.path)):
    sys.path = package_path + sys.path

from lxml import etree

from qgis_urlopener import remote_open_from_qgis
from complex_features import ComplexFeatureSource, noPrefix, load_complex_gml, properties_from_layer, is_layer_complex
from identify_dialog import IdentifyDialog
from creation_dialog import CreationDialog
from table_dialog import TableDialog

import gml2relational
from gml2relational.relational_model_builder import load_gml_model
from gml2relational.sqlite_writer import create_sqlite_from_model
from gml2relational.qgis_project_writer import create_qgis_project_from_model

class IdentifyGeometry(QgsMapToolIdentify):
    geomIdentified = pyqtSignal(QgsVectorLayer, QgsFeature)
    
    def __init__(self, canvas):
        self.canvas = canvas
        QgsMapToolIdentify.__init__(self, canvas)
 
    def canvasReleaseEvent(self, mouseEvent):
        results = self.identify(mouseEvent.x(), mouseEvent.y(), self.TopDownStopAtFirst, self.VectorLayer)
        if len(results) > 0:
            self.geomIdentified.emit(results[0].mLayer, results[0].mFeature)

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

class ProgressDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self, None)
        self.__label = QLabel(self)
        self.__layout = QVBoxLayout()
        self.__layout.addWidget(self.__label)
        self.setLayout(self.__layout)
        self.resize(600, 70)

    def setText(self, text):
        self.__label.setText(text)

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
        self.tableAction = QAction(QIcon(os.path.dirname(__file__) + "/mActionOpenTableGML.svg"), \
                              u"Open feature list", self.iface.mainWindow())
        self.tableAction.triggered.connect(self.onOpenTable)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"Complex Features", self.action)
        self.iface.addToolBarIcon(self.identifyAction)
        self.iface.addPluginToMenu(u"Complex Features", self.identifyAction)
        self.iface.addToolBarIcon(self.tableAction)
        self.iface.addPluginToMenu(u"Complex Features", self.tableAction)
    
    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu(u"Complex Features",self.action)
        self.iface.removeToolBarIcon(self.identifyAction)
        self.iface.removePluginMenu(u"Complex Features",self.identifyAction)
        self.iface.removeToolBarIcon(self.tableAction)
        self.iface.removePluginMenu(u"Complex Features",self.tableAction)

    def onAddLayer(self):
        layer_edited = False
        sel = self.iface.legendInterface().selectedLayers()
        if len(sel) > 0:
            sel_layer = sel[0]
        if sel:
            layer_edited, xml_uri, is_remote, attributes, geom_mapping, output_filename = properties_from_layer(sel_layer)

        if layer_edited:
            creation_dlg = CreationDialog(xml_uri, is_remote, attributes, geom_mapping, output_filename)
        else:
            creation_dlg = CreationDialog()
        r = creation_dlg.exec_()
        if not r:
            return

        if creation_dlg.import_type() == 0:
            is_remote, url = creation_dlg.source()
            mapping = creation_dlg.attribute_mapping()
            geom_mapping = creation_dlg.geometry_mapping()
            output_filename = creation_dlg.output_filename()
            new_layer = load_complex_gml(url, is_remote, mapping, geom_mapping, output_filename)

            do_replace = False
            if creation_dlg.replace_current_layer():
                r = QMessageBox.question(None, "Replace layer ?", "You are about to replace the active layer. Are you sure ?", QMessageBox.Yes | QMessageBox.No)
                if r == QMessageBox.Yes:
                    do_replace = True

            if do_replace:
                replace_layer(sel_layer, new_layer)
            else:
                # a new layer
                QgsMapLayerRegistry.instance().addMapLayer(new_layer)
        else: # import type == 2
            is_remote, url = creation_dlg.source()
            output_filename = creation_dlg.output_filename()
            archive_dir = creation_dlg.archive_directory()
            merge_depth = creation_dlg.merge_depth()
            merge_sequences = creation_dlg.merge_sequences()

            # temporary sqlite file
            tfile = QTemporaryFile()
            tfile.open()
            project_file = tfile.fileName() + ".qgs"
            tfile.close()

            if os.path.exists(output_filename):
                os.unlink(output_filename)

            self.p_widget = ProgressDialog()
            self.p_widget.show()
            def opener(uri):
                self.p_widget.setText("Downloading {} ...".format(uri))
                return remote_open_from_qgis(uri)
            def mylogger(t):
                if isinstance(t, tuple):
                    lvl, msg = t
                else:
                    msg = t
                self.p_widget.setText(msg)
                QCoreApplication.processEvents()
            model = load_gml_model(url, archive_dir,
                                   merge_max_depth = merge_depth,
                                   merge_sequences = merge_sequences,
                                   urlopener = opener,
                                   logger = mylogger)

            self.p_widget.setText("Creating the Spatialite file ...")
            QCoreApplication.processEvents()
            create_sqlite_from_model(model, output_filename)

            self.p_widget.setText("Creating the QGIS project ...")
            QCoreApplication.processEvents()
            create_qgis_project_from_model(model, output_filename, project_file, QgsApplication.srsDbFilePath(), QGis.QGIS_VERSION)
            QgsProject.instance().setFileName(project_file)
            QgsProject.instance().read()
            self.p_widget.hide()

    def onIdentify(self):
        self.mapTool = IdentifyGeometry(self.iface.mapCanvas())
        self.mapTool.geomIdentified.connect(self.onGeometryIdentified)
        self.iface.mapCanvas().setMapTool(self.mapTool)

    def onGeometryIdentified(self, layer, feature):
        # disable map tool
        self.iface.mapCanvas().setMapTool(None)

        self.dlg = IdentifyDialog(layer, feature)
        self.dlg.setWindowModality(Qt.ApplicationModal)
        self.dlg.show()

    def onOpenTable(self):
        layer = self.iface.activeLayer()
        if not is_layer_complex(layer):
            return
        
        self.table = TableDialog(layer)
        self.table.show()
