#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtXml import *
from qgis.core import *
from qgis.gui import *

import os
import pyspatialite.dbapi2 as db

package_path = [os.path.join(os.path.dirname(__file__), "extlibs")]
import sys
if not set(package_path).issubset(set(sys.path)):
    sys.path = package_path + sys.path

from qgis_urlopener import remote_open_from_qgis
from complex_features import ComplexFeatureSource, load_complex_gml, properties_from_layer, is_layer_complex
from creation_dialog import CreationDialog
from model_dialog import ModelDialog
from xml_tree_widget import XMLTreeWidget

import gml2relational
from gml2relational.relational_model_builder import load_gml_model
from gml2relational.relational_model import load_model_from, save_model_to
from gml2relational.sqlite_writer import create_sqlite_from_model
from gml2relational.qgis_project_writer import create_qgis_project_from_model
from gml2relational.uri import URI

import custom_viewers

from . import name as plugin_name
from . import version as plugin_version

# ==============================
def show_viewer(layer, feature, parent, viewer):
    # load the model
    model_file = QgsProject.instance().fileName() + ".model"
    if not os.path.exists(model_file):
        QMessageBox.critical(None, "File not found", "Cannot find the model file")
        return
    model = load_model_from(model_file)
    ds = QgsDataSourceURI(layer.source())
    import sqlite3
    conn = sqlite3.connect(ds.database())
    dlg = QDialog(parent)
    w = viewer.init_from_model(model, conn, feature.attribute("id"), dlg)
    layout = QVBoxLayout()
    layout.addWidget(w)
    dlg.setWindowTitle(w.windowTitle())
    dlg.setLayout(layout)
    dlg.resize(800, 600)
    dlg.show()
    
def find_label_layout(dialog, lbl_text):
    # find the parent layout of a QLabel
    ll = dialog.findChildren(QWidget)
    ll = [l.layout() for l in ll if l.layout() is not None and isinstance(l.layout(), QGridLayout)]
    for l in ll:
        for i in range(l.count()):
            it = l.itemAt(i)
            if isinstance(it, QWidgetItem) and isinstance(it.widget(), QLabel) and it.widget().text() == lbl_text:
                return l
    return None

def add_viewer_to_form(dialog, layer, feature):
    if dialog.findChild(QPushButton,"_viewer_button") is not None:
        return
    tw = [tw for tw in dialog.findChildren(QTabWidget) if tw.tabText(0) == "Columns"][0]
    l = find_label_layout(tw, "id")

    viewers = custom_viewers.get_custom_viewers()
    viewer = [viewer for viewer in viewers.values() if viewer.table_name() == layer.name()][0]
    btn = QPushButton(viewer.icon(), viewer.name() + " plugin", tw)
    btn.setObjectName("_viewer_button")
    btn.clicked.connect(lambda obj, checked = False: show_viewer(layer, feature, tw, viewer))
    l.addWidget(btn, l.rowCount(), 0, Qt.AlignTop)

def add_xml_tree_to_form(dialog, layer, feature):
    w = dialog.findChild(QPushButton, "_xml_widget_")
    if w is not None:
        return
    l = find_label_layout(dialog, "fid")
    if l is None:
        return

    w = XMLTreeWidget(dialog)
    w.setObjectName("_xml_widget_")
    w.updateFeature(feature)
    lbl = QLabel("XML", dialog)
    l.addWidget(lbl, l.rowCount()-1, 0)
    l.addWidget(w, l.rowCount()-1, 1)
    l.setRowStretch(l.rowCount()-1, 2)

def show_viewer_init_code():
    return """
def my_form_open(dialog, layer, feature):
    from gml_application_schema_toolbox import main as mmain
    mmain.add_viewer_to_form(dialog, layer, feature)
"""

def show_xml_init_code():
    return """
def my_form_open(dialog, layer, feature):
    from gml_application_schema_toolbox import main as mmain
    mmain.add_xml_tree_to_form(dialog, layer, feature)
"""

# ===============


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
        self.__progress = QProgressBar(self)
        self.__layout.addWidget(self.__progress)
        self.setLayout(self.__layout)
        self.resize(600, 70)
        self.setFixedSize(600, 70)
        self.__progress.hide()

    def setText(self, text):
        self.__label.setText(text)

    def setProgress(self, i, n):
        self.__progress.show()
        self.__progress.setMinimum(0)
        self.__progress.setMaximum(n)
        self.__progress.setValue(i)

class MainPlugin:

    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        self.action = QAction(QIcon(os.path.dirname(__file__) + "/mActionAddGMLLayer.svg"), \
                              u"Add/Edit Complex Features Layer", self.iface.mainWindow())
        self.action.triggered.connect(self.onAddLayer)

        self.schemaAction = QAction(QIcon(os.path.dirname(__file__) + "/mActionShowSchema.svg"), \
                              u"Show schema", self.iface.mainWindow())
        self.schemaAction.triggered.connect(self.onShowSchema)

        self.aboutAction = QAction("About", self.iface.mainWindow())
        self.aboutAction.triggered.connect(self.onAbout)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(plugin_name(), self.action)
        self.iface.addToolBarIcon(self.schemaAction)
        self.iface.addPluginToMenu(plugin_name(), self.schemaAction)
        self.iface.addPluginToMenu(plugin_name(), self.aboutAction)

        QgsProject.instance().writeProject.connect(self.onProjectWrite)

        self.model_dlg = None
        self.model = None
    
    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu(plugin_name(),self.action)
        self.iface.removeToolBarIcon(self.schemaAction)
        self.iface.removePluginMenu(plugin_name(),self.schemaAction)
        self.iface.removePluginMenu(plugin_name(), self.aboutAction)

    def onAbout(self):
        self.about_dlg = QWidget()
        vlayout = QVBoxLayout()
        l = QLabel(u"""
        <h1>QGIS GML Application Schema Toolbox</h1>
        <h3>Version: {}</h3>
        <p>This plugin is a prototype aiming at experimenting with the manipulation of "Complex Features" streams.</p>
        <p>Two modes are available:
        <ul><li>A mode where the initial XML hierarchical view is preserved. In this mode, an XML instance
        is represented by a unique QGIS vector layer with a column that stores the XML subtree for each feature.
        Augmented tools are available to identify a feature or display the attribute table of the layer.
        Custom QT-based viewers can be run on XML elements of given types.</li>
        <li>A mode where the XML hierarchical data is first converted to a relational database (SQlite).
        In this mode, the data is spread accross different QGIS layers. Links between tables are declared
        as QGIS relations and "relation reference" widgets. It then allows to use the standard QGIS attribute
        table (in "forms" mode) to navigate the relationel model. A tool allows to view the whole schema.</li>
        </ul>
        <p>This plugin has been funded by BRGM and developed by Oslandia.</p>
        """.format(plugin_version()))
        l.setWordWrap(True)
        vlayout.addWidget(l)
        hlayout = QHBoxLayout()
        l2 = QLabel()
        l2.setPixmap(QPixmap(os.path.join(os.path.dirname(__file__), "logo_brgm.svg")).scaledToWidth(200, Qt.SmoothTransformation))
        l3 = QLabel()
        l3.setPixmap(QPixmap(os.path.join(os.path.dirname(__file__), "logo_oslandia.png")).scaledToWidth(200, Qt.SmoothTransformation))
        hlayout.addWidget(l2)
        hlayout.addWidget(l3)
        vlayout.addLayout(hlayout)
        self.about_dlg.setLayout(vlayout)
        self.about_dlg.setWindowTitle(plugin_name())
        self.about_dlg.setWindowModality(Qt.WindowModal)
        self.about_dlg.show()
        self.about_dlg.resize(600,600)
        

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

        class MyLogger:
            def __init__(self, widget):
                self.p_widget = widget
            def text(self, t):
                if isinstance(t, tuple):
                    lvl, msg = t
                else:
                    msg = t
                self.p_widget.setText(msg)
                QCoreApplication.processEvents()
            def progression(self, i, n):
                self.p_widget.setProgress(i, n)
                QCoreApplication.processEvents()

        self.p_widget = ProgressDialog()
        self.p_widget.show()
        try:

            if creation_dlg.import_type() == 0:
                is_remote, url = creation_dlg.source()
                mapping = creation_dlg.attribute_mapping()
                geom_mapping = creation_dlg.geometry_mapping()
                output_filename = creation_dlg.output_filename()
                new_layer = load_complex_gml(url, is_remote, mapping, geom_mapping, output_filename, logger = MyLogger(self.p_widget))

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

                # custom form widget for XML
                new_layer.editFormConfig().setInitCode(show_xml_init_code())
                new_layer.editFormConfig().setInitFunction("my_form_open")
                new_layer.editFormConfig().setInitCodeSource(QgsEditFormConfig.CodeSourceDialog)
                new_layer.editFormConfig().setWidgetType(0, "Hidden") # id
                new_layer.editFormConfig().setWidgetType(2, "Hidden") # _xml_
                new_layer.setDisplayExpression("fid")

            else: # import type == 2
                is_remote, url = creation_dlg.source()
                output_filename = creation_dlg.output_filename()
                archive_dir = creation_dlg.archive_directory()
                merge_depth = creation_dlg.merge_depth()
                merge_sequences = creation_dlg.merge_sequences()
                enforce_not_null = creation_dlg.enforce_not_null()

                # temporary sqlite file
                tfile = QTemporaryFile()
                tfile.open()
                project_file = tfile.fileName() + ".qgs"
                model_file = project_file + ".model"
                tfile.close()

                if os.path.exists(output_filename):
                    os.unlink(output_filename)

                def opener(uri):
                    self.p_widget.setText("Downloading {} ...".format(uri))
                    return remote_open_from_qgis(uri)

                uri = URI(url, opener)
                model = load_gml_model(uri, archive_dir,
                                       merge_max_depth = merge_depth,
                                       merge_sequences = merge_sequences,
                                       urlopener = opener,
                                       logger = MyLogger(self.p_widget))
                save_model_to(model, model_file)

                self.p_widget.setText("Creating the Spatialite file ...")
                QCoreApplication.processEvents()
                create_sqlite_from_model(model, output_filename, enforce_not_null)

                self.p_widget.setText("Creating the QGIS project ...")
                QCoreApplication.processEvents()
                create_qgis_project_from_model(model, output_filename, project_file, QgsApplication.srsDbFilePath(), QGis.QGIS_VERSION)
                QgsProject.instance().setFileName(project_file)
                QgsProject.instance().read()

                # custom viewers initialization
                viewers = custom_viewers.get_custom_viewers()
                table_names = model.tables().keys()
                for viewer in viewers.values():
                    if viewer.table_name() in table_names:
                        print "Init {} viewer on {}".format(viewer.name(), viewer.table_name())
                        layer = QgsMapLayerRegistry.instance().mapLayersByName(viewer.table_name())[0]
                        layer.editFormConfig().setInitCode(show_viewer_init_code())
                        layer.editFormConfig().setInitFunction("my_form_open")
                        layer.editFormConfig().setInitCodeSource(QgsEditFormConfig.CodeSourceDialog)
                    
        except db.IntegrityError as e:
            if "NOT NULL constraint" in str(e):
                QMessageBox.critical(None, "Integrity error", unicode(e) + "\nTry reloading the file without NOT NULL constraints")
        finally:
            self.p_widget.hide()

    def onShowSchema(self):
        # load the model
        model_file = QgsProject.instance().fileName() + ".model"
        if not os.path.exists(model_file):
            QMessageBox.critical(None, "File not found", "Cannot find the model file")
            return

        attribute_table_action = self.iface.mainWindow().findChild((QAction,), "mActionOpenTable")
        def onTableSelected(table_name):
            # make the selected layer the active one
            # and open the attribute table dialog
            layers = QgsMapLayerRegistry.instance().mapLayersByName(table_name)
            if len(layers) == 1:
                layer = layers[0]
                self.iface.setActiveLayer(layer)
                attribute_table_action.trigger()
                        
        self.model = load_model_from(model_file)
        self.model_dlg = ModelDialog(self.model)
        self.model_dlg.tableSelected.connect(onTableSelected)
        self.model_dlg.show()

    def onProjectWrite(self, dom):
        # make sure the model is saved with the project
        if self.model is not None:
            project_file = QgsProject.instance().fileName()
            model_file = project_file + ".model"
            save_model_to(self.model, model_file)
        
