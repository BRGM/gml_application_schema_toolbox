import os

from PyQt4 import QtGui
from PyQt4.QtCore import *
from PyQt4.QtGui import *

import xml.etree.ElementTree as ET

from complex_features import load_complex_gml, is_layer_complex, remote_open_from_qgis
from gml2relational.xml_utils import no_prefix, split_tag, xml_parse, xml_parse_from_string

from qgis.core import QgsMapLayerRegistry

def fill_tree_with_element(widget, treeItem, elt, ns_imap = {}):
    """
    :param widget: the QTreeWidget
    :param treeItem: a QTreeWidgetItem to fill
    :param elt: the XML node
    :param ns_imap: an "inverse" namespace map { uri : prefix }
    """
    # tag
    ns, tag = split_tag(elt.tag)
    if ns and ns_imap.get(ns):
        treeItem.setText(0, ns_imap[ns] + ":" + tag)
    else:
        treeItem.setText(0, tag)
    f = treeItem.font(0)
    f.setBold(True)
    treeItem.setFont(0,f)

    # attributes
    for k, v in elt.attrib.iteritems():
        child = QTreeWidgetItem()
        treeItem.addChild(child)
        if '}' in k:
            i = k.index('}')
            ns = k[1:i]
            # get ns prefix from ns uri
            p = ns_imap.get(ns)
            if p is not None:
                n = p + ":" + k[i+1:]
            else:
                n = k[i+1:]
        else:
            n = no_prefix(k)
        child.setText(0, "@" + n)
        if n == 'xlink:href' and v.startswith('http'):
            html = QLabel(widget)
            html.setOpenExternalLinks(True)
            html.setTextFormat(Qt.RichText)
            html.setText('<a href="{}">{}</a>'.format(v, v))
            #child.setText(1, '<a href="{}">{}</a>'.format(v, v))
            child.setData(1, Qt.UserRole, v)
            widget.setItemWidget(child, 1, html)
        else:
            child.setText(1, v)
    # text
    if elt.text:
        treeItem.setText(1, elt.text)
        
    # children
    for xmlChild in elt:
        child = QTreeWidgetItem()
        treeItem.addChild(child)
        fill_tree_with_element(widget, child, xmlChild, ns_imap)

def recurse_expand(treeItem):
    treeItem.setExpanded(True)
    for i in range(treeItem.childCount()):
        recurse_expand(treeItem.child(i))

def fill_tree_with_xml(treeWidget, xml):
    """
    Fill a QTreeWidget with XML nodes.
    :param treeWidget: a QTreeWidget
    :param xml: the XML content, as string
    """
    doc, ns_map = xml_parse_from_string(xml)
    treeWidget.clear()
    treeWidget.setColumnCount(2)
    ns_imap = {}
    for k, v in ns_map.iteritems():
        ns_imap[v] = k
    fill_tree_with_element(treeWidget, treeWidget.invisibleRootItem(), doc.getroot(), ns_imap)
    recurse_expand(treeWidget.invisibleRootItem())
    treeWidget.resizeColumnToContents(0)
    treeWidget.resizeColumnToContents(1)

class XMLTreeWidget(QtGui.QTreeWidget):
    def __init__(self, parent = None):
        """Constructor.
        :param feature: a QgsFeature
        :param parent: a QWidget parent
        """
        super(XMLTreeWidget, self).__init__(parent)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setWordWrap(True)
        self.setExpandsOnDoubleClick(False)
        self.headerItem().setText(0, "Element")
        self.headerItem().setText(1, "Value")
        self.header().setVisible(True)
        self.header().setCascadingSectionResizes(True)

        self.customContextMenuRequested.connect(self.onContextMenu)

    def updateFeature(self, feature):
        x = None
        try:
            x = feature.attribute('_xml_')
        except KeyError:
            pass
        if x:
            fill_tree_with_xml(self, x)

    def onContextMenu(self, pos):
        row = self.selectionModel().selectedRows()[0]
        menu = QMenu(self)
        copyAction = QAction(u"Copy value", self)
        copyAction.triggered.connect(self.onCopyItemValue)
        copyXPathAction = QAction(u"Copy XPath", self)
        copyXPathAction.triggered.connect(self.onCopyXPath)
        menu.addAction(copyAction)
        menu.addAction(copyXPathAction)

        item = self.currentItem()
        if item.text(0) == '@xlink:href' and item.data(1, Qt.UserRole) and item.data(1, Qt.UserRole).startswith('http'):
            resolveMenu = QMenu("Resolve external", menu)
            resolveEmbeddedAction = QAction(u"Embedded", self)
            resolveEmbeddedAction.triggered.connect(self.onResolveEmbedded)
            resolveMenu.addAction(resolveEmbeddedAction)

            resolveNewLayerAction = QAction(u"As a new layer", self)
            resolveNewLayerAction.triggered.connect(self.onResolveNewLayer)
            resolveMenu.addAction(resolveNewLayerAction)

            addToMenu = QMenu("Add to layer", menu)
            addToEmpty = True
            for id, l in QgsMapLayerRegistry.instance().mapLayers().iteritems():
                if is_layer_complex(l):
                    action = QAction(l.name(), addToMenu)
                    action.triggered.connect(lambda checked, layer=l: self.onResolveAddToLayer(layer))
                    addToMenu.addAction(action)
                    addToEmpty = False
            if not addToEmpty:
                resolveMenu.addMenu(addToMenu)

            menu.addMenu(resolveMenu)

        menu.popup(self.mapToGlobal(pos))

    def onCopyXPath(self):
        def get_xpath(item):
            s = ''
            if item.parent():
                s = get_xpath(item.parent())
            return s + "/" + item.text(0)

        xpath = get_xpath(self.currentItem())
        QApplication.clipboard().setText(xpath)

    def onCopyItemValue(self):
        t = self.currentItem().text(1)
        if not t:
            t = self.currentItem().data(1, Qt.UserRole)
        QApplication.clipboard().setText(t)

    def onResolveEmbedded(self):
        item = self.currentItem()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        uri = item.data(1, Qt.UserRole)
        try:
            f = remote_open_from_qgis(uri)
            try:
                doc, ns_map = xml_parse(f)
            except ParseError:
                # probably not an XML
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, "XML parsing error", "The external resource is not a well formed XML")
                return

            ns_imap = {}
            for k, v in ns_map.iteritems():
                ns_imap[v] = k
            fill_tree_with_element(self, item.parent(), doc.getroot(), ns_imap)
        finally:
            QApplication.restoreOverrideCursor()

    def onResolveNewLayer(self):
        item = self.currentItem()
        uri = item.data(1, Qt.UserRole)
        new_layer = load_complex_gml(uri, True)
        if new_layer:
            QgsMapLayerRegistry.instance().addMapLayer(new_layer)

    def onResolveAddToLayer(self, layer, checked=False):
        item = self.currentItem()
        uri = item.data(1, Qt.UserRole)
        new_layer = load_complex_gml(uri, True)
        if new_layer:
            # read the feature from the new_layer and insert it in the selected layer
            f_in = next(new_layer.getFeatures())
            pr = layer.dataProvider()
            # FIXME test layer compatibility ?
            pr.addFeatures([f_in])
            

