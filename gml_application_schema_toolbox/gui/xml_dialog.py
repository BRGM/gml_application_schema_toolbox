"""
/***************************************************************************
 CapabilitiesDialog
                                 A QGIS plugin
 GMLAS Plugin
                             -------------------
        begin                : 2016-09-21
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Arnaud Morvan - www.camptocamp.com
        email                : arnaud.morvan@camptocamp.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.PyQt.QtXml import QDomDocument, QDomNode

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'xml_dialog.ui'))


class DomNodeItem(QStandardItem):

    def __init__(self, node):
        super(DomNodeItem, self).__init__()
        self._node = node
        self.setText(self.getText())

        child = node.firstChild()
        while not child.isNull():
            self.appendRow(DomNodeItem(child))
            child = child.nextSibling()

    def getText(self):
        if self._node.isElement():
            return "<{}>".format(self._node.nodeName())

        if self._node.isText():
            return self._node.nodeValue()

        if self._node.nodeType() == QDomNode.AttributeNode:
            return "attribute: {}: {}".format(self._node.nodeName(), self._node.nodeValue())

        if self._node.nodeValue():
            return "{}: {}".format(self._node.nodeName(), self._node.nodeValue())
        return self._node.nodeName()


class DomDocumentModel(QStandardItemModel):

    def __init__(self, document, parent=None):
        super(DomDocumentModel, self).__init__(parent)
        self._document = document

        root = document.documentElement()
        child = root.firstChild()
        while not child.isNull():
            self.appendRow(DomNodeItem(child))
            child = child.nextSibling()


class XmlDialog(BASE, WIDGET):

    def __init__(self, parent=None, xml=None):
        super(XmlDialog, self).__init__(parent)
        self.setupUi(self)

        # self.setWindowTitle(wfs.identification.title)

        document = QDomDocument()
        document.setContent(xml)
        model = DomDocumentModel(document)
        self.treeView.setModel(model)
