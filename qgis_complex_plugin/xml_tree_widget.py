import os

from PyQt4 import QtGui
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from lxml import etree

from complex_features import noPrefix

import urllib

def fill_tree_with_element(widget, treeItem, elt):
    # tag
    if elt.prefix:
        treeItem.setText(0, elt.prefix + ':' + noPrefix(elt.tag))
    else:
        treeItem.setText(0, noPrefix(elt.tag))
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
            n = elt.nsmap.keys()[elt.nsmap.values().index(ns)] + ":" + k[i+1:]
        else:
            n = noPrefix(k)
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
        if isinstance(xmlChild, etree._Comment):
            continue
        child = QTreeWidgetItem()
        treeItem.addChild(child)
        fill_tree_with_element(widget, child, xmlChild)

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
    tree = etree.XML(xml)
    treeWidget.clear()
    treeWidget.setColumnCount(2)
    fill_tree_with_element(treeWidget, treeWidget.invisibleRootItem(), tree)
    recurse_expand(treeWidget.invisibleRootItem())
    treeWidget.resizeColumnToContents(0)
    treeWidget.resizeColumnToContents(1)

class XMLTreeWidget(QtGui.QTreeWidget):
    def __init__(self, feature, parent = None):
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

        self.itemDoubleClicked.connect(self.onItemDoubleClicked)
        self.customContextMenuRequested.connect(self.onContextMenu)

        self.updateFeature(feature)

    def updateFeature(self, feature):
        self.clear()
        x = None
        try:
            x = feature.attribute('_xml_')
        except KeyError:
            pass
        if x:
            fill_tree_with_xml(self, x)

    def onItemDoubleClicked(self, item, column):
        if item.text(0) == '@xlink:href' and item.data(1, Qt.UserRole).startswith('http'):
            QApplication.setOverrideCursor(Qt.WaitCursor)
            uri = item.data(1, Qt.UserRole)
            try:
                f = urllib.urlopen(uri)
                try:
                    xml = etree.parse(f)
                except etree.XMLSyntaxError:
                    # probably not an XML
                    return

                fill_tree_with_element(self, item.parent(), xml.getroot())
            finally:
                QApplication.restoreOverrideCursor()

    def onContextMenu(self, pos):
        row = self.selectionModel().selectedRows()[0]
        menu = QMenu(self)
        copyAction = QAction(u"Copy value", self)
        #copyAction.triggered.connect(self.onCopyItemValue)
        copyXPathAction = QAction(u"Copy XPath", self)
        copyXPathAction.triggered.connect(self.onCopyXPath)
        menu.addAction(copyAction)
        menu.addAction(copyXPathAction)
        menu.popup(self.mapToGlobal(pos))

    def onCopyXPath(self):
        def get_xpath(item):
            s = ''
            if item.parent():
                s = get_xpath(item.parent())
            return s + "/" + item.text(0)

        # make sure to select the first column
        idx = self.indexFromItem(self.currentItem())
        idx = idx.sibling(idx.row(), 0)
        item = self.itemFromIndex(idx)
        
        xpath = get_xpath(item)
        QApplication.clipboard().setText(xpath)
