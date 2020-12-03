
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

"""Functions to inject a custom QT widget in a QGIS form

This module contains functions that allow the user to "inject"
a custom QT widget in an existing QGIS feature form. This allows
to extend the default feature form dialog with a custom widget.
This mechanism is used for example to display an XML widget.
"""

__all__ = ["install_xml_tree_on_feature_form"]

from qgis.PyQt.QtWidgets import QWidget, QGridLayout, QWidgetItem, QLabel, QPushButton, QTabWidget
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QSpacerItem, QSizePolicy, QLineEdit
from qgis.core import QgsEditFormConfig, QgsDataSourceUri, QgsProject, QgsField, QgsRelation
from qgis.core import QgsAttributeEditorField, QgsAttributeEditorRelation, QgsEditorWidgetSetup

from . import xml_tree_widget
from ..core.xml_utils import no_ns
from .custom_viewers import get_custom_viewers
from .wait_cursor_context import WaitCursor

def install_xml_tree_on_feature_form(lyr):
    """Install an XML tree on feature form of the input layer"""
    
    code = ("def my_form_open(dialog, layer, feature):\n"
            "    from gml_application_schema_toolbox.gui import qgis_form_custom_widget as qq\n"
            "    qq.inject_xml_tree_into_form(dialog, feature)\n")
    conf = lyr.editFormConfig()
    conf.setInitCode(code)
    conf.setInitFunction("my_form_open")
    conf.setInitCodeSource(QgsEditFormConfig.CodeSourceDialog)
    lyr.setEditFormConfig(conf)

def install_viewer_on_feature_form(lyr):
    """Install a custom viewer button on feature form of the input layer"""
    
    code = ("def my_form_open(dialog, layer, feature):\n"
            "    from gml_application_schema_toolbox.gui import qgis_form_custom_widget as qq\n"
            "    qq.inject_custom_viewer_into_form(dialog, layer, feature)\n"
            "    qq.inject_href_buttons_into_form(dialog, layer, feature)\n"
    )
    conf = lyr.editFormConfig()
    conf.setInitCode(code)
    conf.setInitFunction("my_form_open")
    conf.setInitCodeSource(QgsEditFormConfig.CodeSourceDialog)
    lyr.setEditFormConfig(conf)

def inject_custom_viewer_into_form(dialog, layer, feature):
    """Ass a custom viewer button on a form if needed.
    Used by the "relational mode" """
    if feature.attributes() == []:
        # don't do anything if we don't have a feature
        return

    tab = dialog.findChildren(QTabWidget)[0]
    if tab.count() == 3 and tab.tabText(2) == "Custom viewer":
        # already there
        return

    xpath = no_ns(layer.customProperty("xpath", ""))
    viewer = None
    for viewer_cls, filter in get_custom_viewers().values():
        tag = viewer_cls.xml_tag()
        # remove namespace from tag
        tag = tag[tag.find("}")+1:]
        if tag == xpath:
            # found the viewer
            viewer = viewer_cls
            break
    if viewer is None:
        return

    # get current id
    pkid = layer.customProperty("pkid")
    id = feature[pkid]

    # get db connection settings
    if '.sqlite' in layer.source():
        provider = "SQLite"
        schema = ""
        db_uri, layer_name = layer.source().split("|")
        layer_name = layer_name.split('=')[1]
    else:
        provider = "PostgreSQL"
        ds = QgsDataSourceUri(layer.source())
        db_uri = "PG:" + ds.connectionInfo()
        layer_name = ds.table()
        schema = ds.schema()

    w = viewer_cls.init_from_db(db_uri, provider, schema, layer_name, pkid, id, tab)
    def on_tab_changed(index):
        if index == 2:
            w.resize(400,400)
    # create a new tab
    tab.addTab(w, viewer_cls.icon(), "Custom viewer")
    tab.currentChanged.connect(on_tab_changed)

def inject_href_buttons_into_form(dialog, layer, feature):
    if feature.attributes() == []:
        # don't do anything if we don't have a feature
        return
    # find the layout
    pkid = layer.customProperty("pkid")
    if pkid is None:
        return
    # list of fields that are a xlink:href
    href_fields = layer.customProperty("href_fields", [])
    # list of href URL that have been resolved
    href_resolved = layer.customProperty("href_resolved", [])
    # dict that stores which layer is the resolved href, for each href field
    href_linked_layers = layer.customProperty("href_linked_layers", {})

    layout = __find_label_layout(dialog, pkid)
    for i in range(layout.rowCount()):
        item = layout.itemAtPosition(i, 0)
        if item is None or not isinstance(item.widget(), QLabel):
            continue
        field_name = layout.itemAtPosition(i, 0).widget().text()
        if field_name in href_fields:
            w = layout.itemAtPosition(i, 1).widget()
            href = feature[field_name]
            if href not in href_resolved:
                # add a tool button
                btn = QPushButton("Load", dialog)
                btn.clicked.connect(lambda checked, dlg=dialog, l=layer, f=feature, fd=field_name: on_resolve_href(dlg, l, f, fd))
                w.layout().insertWidget(0, btn)

def on_resolve_href(dialog, layer, feature, field):
    with WaitCursor():
        return on_resolve_href_(dialog, layer, feature, field)

def on_resolve_href_(dialog, layer, feature, field):
    """
    @param dialog the dialog where the feature form is opened
    @param layer the layer on which the href link stands
    @param feature the current feature
    @param field the field name storing the href URL
    @param linked_layer_id the QGIS layer id of the already resolved layer, for update
    """
    from .import_gmlas_panel import ImportGmlasPanel
    path = feature[field]
    if not path:
        return

    # if parent is a Dialog, we are in a feature form
    # else in a attribute table
    is_feature_form = isinstance(dialog.parent, QDialog)

    # The href is resolved thanks to the OGR GMLAS driver.
    # We need to determine what is the "root" layer of the imported
    # href, so that we can connect the xlink:href link to the
    # newly loaded set of layers.
    # There seems to be no way to determine what is the "root" layer
    # of a GMLAS database.
    # So, we rely on XML parsing to determine the root element
    # and on layer xpath found in metadata

    # Download the file so that it is used for XML parsing
    # and for GMLAS loading
    from ..core.qgis_urlopener import remote_open_from_qgis
    from ..core.gml_utils import extract_features_from_file
    from ..core.xml_utils import no_ns, no_prefix
    import tempfile

    with remote_open_from_qgis(path) as fi:
        with tempfile.NamedTemporaryFile(delete=False) as fo:
            fo.write(fi.read())
            tmp_file = fo.name

    _, _, nodes = extract_features_from_file(tmp_file)
    if not nodes:
        raise RuntimeError("No feature found in linked document")
    root_tag = nodes[0].tag

    # reuse the GMLAS import panel widget
    dlg = QDialog()
    import_widget = ImportGmlasPanel(dlg, gml_path=tmp_file)
    path_edit = QLineEdit(path, dlg)
    path_edit.setEnabled(False)
    btn = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
    layout = QVBoxLayout()
    layout.addWidget(path_edit)
    layout.addWidget(import_widget)
    layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
    layout.addWidget(btn)
    dlg.setLayout(layout)
    btn.accepted.connect(dlg.accept)
    btn.rejected.connect(dlg.reject)
    dlg.resize(400, 300)
    dlg.setWindowTitle("Options for xlink:href loading")
    if not dlg.exec_():
        return

    # close the current form
    w = dialog
    while not isinstance(w, QDialog):
        w = w.parent()
    w.close()

    import_widget.do_load()
    # Add a link between the current layer
    # and the root layer of the newly loaded (complex) features

    # 1. determine the root layer and pkid of all its features
    root_layer = None
    for l in QgsProject.instance().mapLayers().values():
        if no_ns(l.customProperty("xpath", "")) == no_prefix(root_tag):
            root_layer = l
            break
    if root_layer is None:
        raise RuntimeError("Cannot determine the root layer")

    pkid = layer.customProperty("pkid")
    pkid_value = feature[pkid]
    root_layer.startEditing()
    # 2. add a href_origin_pkid field in the root layer
    if "parent_href_pkid" not in [f.name() for f in root_layer.fields()]:
        new_field = QgsField(layer.fields().field(pkid))
        new_field.setName("parent_href_pkid")
        root_layer.addAttribute(new_field)

    # 3. set its value to the id of current feature
    ids_to_change=[]
    for f in root_layer.getFeatures():
        if f["parent_href_pkid"] is None:
            ids_to_change.append(f.id())
    idx = root_layer.fields().indexFromName("parent_href_pkid")
    for fid in ids_to_change:
        # sets the pkid_value
        root_layer.changeAttributeValue(fid, idx, pkid_value)

    root_layer.commitChanges()
    
    # 4. declare a new QgsRelation
    rel_name = "1_n_"+layer.name()+"_"+field
    rel = QgsProject.instance().relationManager().relations().get(rel_name)
    if rel is None:
        rel = QgsRelation()
        rel.setId(rel_name)
        rel.setName(field)
        rel.setReferencedLayer(layer.id())
        rel.setReferencingLayer(root_layer.id())
        rel.addFieldPair("parent_href_pkid", pkid)
        QgsProject.instance().relationManager().addRelation(rel)
    
    # 5. declare the new relation in the form widgets
    # new 1:N in the current layer
    fc = layer.editFormConfig()
    rel_tab = fc.tabs()[1]
    rel_tab.addChildElement(QgsAttributeEditorRelation(rel.name(), rel, rel_tab))
    # new field in the root layer
    fc = root_layer.editFormConfig()
    main_tab = fc.tabs()[0]
    main_tab.addChildElement(QgsAttributeEditorField("parent_href_pkid", idx, main_tab))
    # declare as reference relation widget
    s = QgsEditorWidgetSetup("RelationReference", {'AllowNULL': False,
                                                   'ReadOnly': True,
                                                   'Relation': rel.id(),
                                                   'OrderByValue': False,
                                                   'MapIdentification': False,
                                                   'AllowAddFeatures': False,
                                                   'ShowForm': True})
    root_layer.setEditorWidgetSetup(idx, s)
    
    # write metadata in layers
    href_resolved = layer.customProperty("href_resolved", [])
    if path not in href_resolved:
        layer.setCustomProperty("href_resolved", href_resolved + [path])
    href_linked_layers = layer.customProperty("href_linked_layers", {})
    href_linked_layers[field] = root_layer.id()
    layer.setCustomProperty("href_linked_layers", href_linked_layers)
        
    # 6. reload the current form
    from ..main import get_iface    
    if is_feature_form:
        get_iface().openFeatureForm(layer, feature)
    else:
        get_iface().showAttributeTable(layer)

def inject_xml_tree_into_form(dialog, feature):
    """Function called on form opening to add a custom XML widget"""
    w = dialog.findChild(QPushButton, "_xml_widget_")
    if w is not None:
        return
    l = __find_label_layout(dialog, "fid")
    if l is None:
        return

    w = xml_tree_widget.XMLTreeWidget(dialog)
    w.setObjectName("_xml_widget_")
    w.updateFeature(feature)
    lbl = QLabel("XML", dialog)
    l.addWidget(lbl, l.rowCount()-1, 0)
    l.addWidget(w, l.rowCount()-1, 1)
    l.setRowStretch(l.rowCount()-1, 2)

    # the tree widget must not be garbage collected yet
    # since we want its Python slots to be called on signals
    # we then transfer its ownership to a C++ object that lives longer
    import sip
    sip.transferto(w, dialog)

def __find_label_layout(dialog, lbl_text):
    """Find the parent layout of a QLabel in a dialog"""
    ll = dialog.findChildren(QWidget)
    ll = [l.layout() for l in ll if l.layout() is not None and isinstance(l.layout(), QGridLayout)]
    for l in ll:
        for i in range(l.count()):
            it = l.itemAt(i)
            if isinstance(it, QWidgetItem) and isinstance(it.widget(), QLabel) and it.widget().text().startswith(lbl_text):
                return l
    return None
