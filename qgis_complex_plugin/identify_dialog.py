import os

from PyQt4 import QtGui, uic
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from lxml import etree

from complex_features import noPrefix

import urllib

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'identify_dialog.ui'))

def fill_tree_with_element(widget, treeItem, elt, inv_nsmap = None):
    # attributes
    for k, v in elt.attrib.iteritems():
        child = QTreeWidgetItem()
        treeItem.addChild(child)
        if inv_nsmap and '}' in k:
            i = k.index('}')
            ns = k[1:i]
            n = inv_nsmap[ns] + ":" + k[i+1:]
        else:
            n = noPrefix(k)
        child.setText(0, "@" + n)
        if n == 'href' and v.startswith('http'):
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
        if xmlChild.prefix:
            child.setText(0, xmlChild.prefix + ':' + noPrefix(xmlChild.tag))
        else:
            child.setText(0, noPrefix(xmlChild.tag))
        f = child.font(0)
        f.setBold(True)
        child.setFont(0,f)
        fill_tree_with_element(widget, child, xmlChild, inv_nsmap)
        treeItem.addChild(child)

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
    # create an inverse map to map namespace uri to namespace prefix
    inv_nsmap = {}
    for k, v in tree.nsmap.iteritems():
        inv_nsmap[v] = k
    fill_tree_with_element(treeWidget, treeWidget.invisibleRootItem(), tree, inv_nsmap)
    recurse_expand(treeWidget.invisibleRootItem())
    treeWidget.resizeColumnToContents(0)

class IdentifyDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, layer, feature, parent=None):
        """Constructor.
        :param layer: QgsVectorLayer the feature is from
        :param feature: a QgsFeature
        """
        super(IdentifyDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # install signals
        self.treeWidget.itemDoubleClicked.connect(self.onItemDoubleClicked)
        self.treeWidget.customContextMenuRequested.connect(self.onContextMenu)

        for i in range(layer.fields().count()):
            field = layer.fields().at(i)
            if field.name() == "_xml_":
                continue
            lineEdit = QLineEdit(feature.attribute(field.name()) or "")
            lineEdit.setReadOnly(True)
            self.formLayout.addRow(field.name(), lineEdit)

        fill_tree_with_xml(self.treeWidget, feature.attribute('_xml_'))
        
    def onItemDoubleClicked(self, item, column):
        if item.text(0) == '@href' and item.data(1, Qt.UserRole).startswith('http'):
            QApplication.setOverrideCursor(Qt.WaitCursor)
            uri = item.data(1, Qt.UserRole)
            try:
                f = urllib.urlopen(uri)
                try:
                    xml = etree.parse(f)
                except etree.XMLSyntaxError:
                    # probably not an XML
                    return

                fill_tree_with_element(self.treeWidget, item.parent(), xml.getroot())
            finally:
                QApplication.restoreOverrideCursor()
    def onContextMenu(self, pos):
        row = self.treeWidget.selectionModel().selectedRows()[0]
        menu = QMenu(self.treeWidget)
        copyAction = QAction(u"Copy value", self.treeWidget)
        #copyAction.triggered.connect(self.onCopyItemValue)
        copyXPathAction = QAction(u"Copy XPath", self.treeWidget)
        copyXPathAction.triggered.connect(self.onCopyXPath)
        menu.addAction(copyAction)
        menu.addAction(copyXPathAction)
        menu.popup(self.treeWidget.mapToGlobal(pos))

    def onCopyXPath(self):
        def get_xpath(item):
            s = ''
            if item.parent():
                s = get_xpath(item.parent())
            return s + "/" + item.text(0)

        # make sure to select the first column
        idx = self.treeWidget.indexFromItem(self.treeWidget.currentItem())
        idx = idx.sibling(idx.row(), 0)
        item = self.treeWidget.itemFromIndex(idx)
        
        xpath = get_xpath(item)
        QApplication.clipboard().setText(xpath)
        
