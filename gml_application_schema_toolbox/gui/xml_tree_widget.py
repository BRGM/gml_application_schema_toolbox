#   Copyright (C) 2017 BRGM (http:///brgm.fr)
#   Copyright (C) 2017 Oslandia <infos@oslandia.com>
#
#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Library General Public
#   License as published by the Free Software Foundation; either
#   version 2 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Library General Public License for more details.
#   You should have received a copy of the GNU Library General Public
#   License along with this library; if not, see <http://www.gnu.org/licenses/>.


import xml.etree.ElementTree as ET
from builtins import next, range

from qgis.core import QgsEditorWidgetSetup, QgsProject
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QAction,
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSpacerItem,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from ..core.load_gml_as_xml import is_layer_gml_xml, load_as_xml_layer
from ..core.qgis_urlopener import remote_open_from_qgis
from ..core.xml_utils import no_prefix, split_tag, xml_parse, xml_parse_from_string
from . import qgis_form_custom_widget
from .custom_viewers import get_custom_viewers


def fill_tree_with_element(
    widget, treeItem, elt, ns_imap={}, custom_viewers={}, ns_map={}
):
    """
    :param widget: the QTreeWidget
    :param treeItem: a QTreeWidgetItem to fill
    :param elt: the XML node
    :param ns_imap: an "inverse" namespace map { uri : prefix }
    :param custom_viewers: a dict giving a custom viewer plugin (QWidget) for some \
        elements {tag : constructor}
    :param ns_map: a namespace map { prefix : uri }
    """
    is_root = treeItem == widget.invisibleRootItem()
    # tag
    ns, tag = split_tag(elt.tag)
    if ns and ns_imap.get(ns):
        treeItem.setText(0, ns_imap[ns] + ":" + tag)
    else:
        treeItem.setText(0, tag)
    f = treeItem.font(0)
    f.setBold(True)
    treeItem.setFont(0, f)

    # custom viewer
    if elt.tag in custom_viewers:
        custom_viewer_widget, fltr = custom_viewers[elt.tag]
        if fltr is None or elt.find(fltr, ns_map) is not None:
            btn = QToolButton(widget)
            btn.setIcon(custom_viewer_widget.icon())
            btn.setIconSize(QSize(32, 32))

            def show_viewer(btn):
                widget.w = custom_viewer_widget.init_from_xml(elt)
                widget.w.setWindowModality(Qt.WindowModal)
                widget.w.show()

            btn.clicked.connect(show_viewer)

            w = QWidget(widget)
            lyt = QHBoxLayout()
            lyt.addWidget(btn)
            lyt.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding))
            w.setLayout(lyt)
            if is_root:
                # insert an item
                child = QTreeWidgetItem()
                treeItem.addChild(child)
                widget.setItemWidget(child, 0, w)
            else:
                widget.setItemWidget(treeItem, 1, w)

    # attributes
    for k, v in elt.attrib.items():
        child = QTreeWidgetItem()
        treeItem.addChild(child)
        if "}" in k:
            i = k.index("}")
            ns = k[1:i]
            # get ns prefix from ns uri
            p = ns_imap.get(ns)
            if p is not None:
                n = p + ":" + k[i + 1 :]
            else:
                n = k[i + 1 :]
        else:
            n = no_prefix(k)
        child.setText(0, "@" + n)
        if n == "xlink:href" and v.startswith("http"):
            html = QLabel(widget)
            html.setOpenExternalLinks(True)
            html.setTextFormat(Qt.RichText)
            html.setText('<a href="{}">{}</a>'.format(v, v))
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
        fill_tree_with_element(widget, child, xmlChild, ns_imap, custom_viewers, ns_map)


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
    for k, v in ns_map.items():
        ns_imap[v] = k
    fill_tree_with_element(
        treeWidget,
        treeWidget.invisibleRootItem(),
        doc.getroot(),
        ns_imap,
        get_custom_viewers(),
        ns_map,
    )
    recurse_expand(treeWidget.invisibleRootItem())
    treeWidget.resizeColumnToContents(0)
    treeWidget.resizeColumnToContents(1)


class XMLTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        """Constructor.
        :param swap_xy: whether to force X/Y coordinate swapping
        :param parent: a QWidget parent
        """
        super(XMLTreeWidget, self).__init__(parent)

        self.swap_xy = False
        self.swap_xy_menu_action = None

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
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
            x = feature.attribute("_xml_")
        except KeyError:
            pass
        if x:
            fill_tree_with_xml(self, x)

    def onContextMenu(self, pos):
        menu = QMenu(self)
        copyAction = QAction("Copy value", self)
        copyAction.triggered.connect(self.onCopyItemValue)
        copyXPathAction = QAction("Copy XPath", self)
        copyXPathAction.triggered.connect(self.onCopyXPath)
        menu.addAction(copyAction)
        menu.addAction(copyXPathAction)

        item = self.currentItem()
        if (
            item.text(0) == "@xlink:href"
            and item.data(1, Qt.UserRole)
            and item.data(1, Qt.UserRole).startswith("http")
        ):
            resolveMenu = QMenu("Resolve external", menu)

            swap_xy_menu_action = QAction("Swap X/Y", self)
            swap_xy_menu_action.setCheckable(True)
            swap_xy_menu_action.setChecked(self.swap_xy)
            swap_xy_menu_action.triggered.connect(self.onSwapXY)
            resolveMenu.addAction(swap_xy_menu_action)

            resolveEmbeddedAction = QAction("Embedded", self)
            resolveEmbeddedAction.triggered.connect(self.onResolveEmbedded)
            resolveMenu.addAction(resolveEmbeddedAction)

            resolveNewLayerAction = QAction("As a new layer", self)
            resolveNewLayerAction.triggered.connect(self.onResolveNewLayer)
            resolveMenu.addAction(resolveNewLayerAction)

            addToMenu = QMenu("Add to layer", menu)
            addToEmpty = True
            for lid, lyr in QgsProject.instance().mapLayers().items():
                if is_layer_gml_xml(lyr):
                    action = QAction(lyr.name(), addToMenu)
                    action.triggered.connect(
                        lambda checked, layer=lyr: self.onResolveAddToLayer(layer)
                    )
                    addToMenu.addAction(action)
                    addToEmpty = False
            if not addToEmpty:
                resolveMenu.addMenu(addToMenu)

            menu.addMenu(resolveMenu)

        menu.popup(self.mapToGlobal(pos))

    def onSwapXY(self, checked):
        self.swap_xy = checked

    def onCopyXPath(self):
        def get_xpath(item):
            s = ""
            if item.parent():
                s = get_xpath(item.parent())
            t = item.text(0)
            if ":" in t:
                tt = t.split(":")[1]
            else:
                tt = t
            if t[0] == "@":
                tt = "@" + tt
            if s == "":
                return tt
            return s + "/" + tt

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
            except ET.ParseError:
                # probably not an XML
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(
                    self,
                    "XML parsing error",
                    "The external resource is not a well formed XML",
                )
                return

            ns_imap = {}
            for k, v in ns_map.items():
                ns_imap[v] = k
            fill_tree_with_element(
                self,
                item.parent(),
                doc.getroot(),
                ns_imap,
                get_custom_viewers(),
                ns_map,
            )
        except RuntimeError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Network error", e.args[0])
            return
        finally:
            QApplication.restoreOverrideCursor()

    def onResolveNewLayer(self):
        item = self.currentItem()
        uri = item.data(1, Qt.UserRole)
        new_layers = load_as_xml_layer(uri, True, swap_xy=self.swap_xy)
        for new_layer in new_layers.values():
            # install an XML tree widget
            qgis_form_custom_widget.install_xml_tree_on_feature_form(new_layer)

            # id column
            new_layer.setEditorWidgetSetup(0, QgsEditorWidgetSetup("Hidden", {}))
            # _xml_ column
            new_layer.setEditorWidgetSetup(2, QgsEditorWidgetSetup("Hidden", {}))
            new_layer.setDisplayExpression("fid")

            QgsProject.instance().addMapLayer(new_layer)

    def onResolveAddToLayer(self, layer, checked=False):
        item = self.currentItem()
        uri = item.data(1, Qt.UserRole)
        new_layer = load_as_xml_layer(uri, True, self.swap_xy)
        if new_layer:
            # read the feature from the new_layer and insert it in the selected layer
            f_in = next(new_layer.getFeatures())
            pr = layer.dataProvider()
            # FIXME test layer compatibility ?
            pr.addFeatures([f_in])
