import os

from PyQt4 import QtGui, uic
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from lxml import etree

from complex_features import noPrefix

import urllib

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'identify_dialog.ui'))

def fill_tree_with_element(widget, treeItem, elt):
    # attributes
    for k, v in elt.attrib.iteritems():
        child = QTreeWidgetItem()
        n = noPrefix(k)
        treeItem.addChild(child)
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
        child = QTreeWidgetItem()
        if xmlChild.prefix:
            child.setText(0, xmlChild.prefix + ':' + noPrefix(xmlChild.tag))
        else:
            child.setText(0, noPrefix(xmlChild.tag))
        f = child.font(0)
        f.setBold(True)
        child.setFont(0,f)
        fill_tree_with_element(widget, child, xmlChild)
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
    fill_tree_with_element(treeWidget, treeWidget.invisibleRootItem(), tree)
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

        for i in range(layer.fields().count()):
            field = layer.fields().at(i)
            if field.name() == "_xml_":
                continue
            lineEdit = QLineEdit(feature.attribute(field.name()))
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
            
