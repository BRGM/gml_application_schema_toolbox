import sys

sys.path.append("/home/hme/src/QGIS/build/output/python")

import xml.etree.ElementTree as ET

from qgis.core import QgsApplication, QgsVectorLayer, QgsMapLayerRegistry, QgsProject, QgsRelation
from PyQt4.QtCore import QFileInfo

app = None

def qgis_project_from_model(tables, tables_rows, root_name, sqlite_file, qgis_file):
    global app
    if app is None:
        app = QgsApplication(sys.argv, True)
        app.setPrefixPath("/home/hme/src/QGIS/build/output", True)
        app.initQgis()

    # load a layer for each table
    layers = {}
    root_group = QgsProject.instance().layerTreeRoot()
    main_group = root_group.addGroup(root_name)
    child_group = main_group.addGroup(u"linked tables")
    child_group.setExpanded(False)
    geom_group = main_group.addGroup(u"geometries")
    geom_group.setExpanded(True)
    for table_name, table in tables.iteritems():
        geometry = table.geometries()[0].name() if len(table.geometries()) > 0 else None
        src = "dbname='{}' table=\"{}\"{} sql=".format(sqlite_file, table.name(), " (" + geometry + ")" if geometry is not None else "")
        l = QgsVectorLayer(src, table.name(), "spatialite")
        layers[table.name()] = l
        QgsMapLayerRegistry.instance().addMapLayer(l, False) # do not add to the legend
        if table_name == root_name:
            main_group.insertLayer(0, l)
        elif geometry is not None:
            geom_group.addLayer(l)
        else:
            child_group.addLayer(l)


    # declare relations
    for table_name, table in tables.iteritems():
        for link in table.links():
            if link.max_occurs() is None:
                continue

            rel = QgsRelation()
            referencingLayer = layers[table.name()]
            referencingField = link.name() + "_id"
            referencedLayer = layers[link.ref_table().name()]
            referencedField = "id"
            rel.setReferencedLayer(referencedLayer.id())
            rel.setReferencingLayer(referencingLayer.id())
            rel.addFieldPair(referencingField, referencedField)
            rel.setRelationName(table.name() + "_" + link.name())
            rel.setRelationId(table.name() + "_" + link.name())
            if not rel.isValid():
                raise RuntimeError("not valid")
            QgsProject.instance().relationManager().addRelation(rel)
        for bl in table.back_links():
            # create a relation for this backlink
            rel = QgsRelation()
            referencingLayer = layers[table.name()]
            referencingField = bl.ref_table().name() + u"_id"
            referencedLayer = layers[bl.ref_table().name()]
            referencedField = "id"
            rel.setReferencedLayer(referencedLayer.id())
            rel.setReferencingLayer(referencingLayer.id())
            rel.addFieldPair(referencingField, referencedField)
            rel.setRelationName(table.name())
            rel.setRelationId(table.name())
            QgsProject.instance().relationManager().addRelation(rel)

            # set the layer's edit widget to "relation reference"
            #field_idx = referencingLayer.fieldNameIndex(referencingField)
            #print("********* field_idx", field_idx)
            #referencingLayer.editFormConfig().setWidgetType(field_idx, "RelationReference")

    fi = QFileInfo(qgis_file)
    QgsProject.instance().write(fi)
    QgsApplication.exitQgis()

    simple_back_links = {}
    for table_name, table in tables.iteritems():
        for link in table.links():
            print(table_name, "links to", link.ref_table().name(), "via", link.name())
            if link.max_occurs() == 1:
                dest_table = link.ref_table().name()
                simple_back_links[dest_table] = (simple_back_links.get(dest_table) or []) + [(table_name, link)]

    doc = ET.parse(qgis_file)
    root = doc.getroot()
    for child in root:
        if child.tag == "projectlayers":
            for layer in child:
                for field in layer:
                    if field.tag == "layername":
                        layer_name = field.text
                    if field.tag == "annotationform" or field.tag == "editform":
                        field.text = "."
                    if field.tag == "editorlayout":
                        field.text = "tablayout"

                #raw_input()
                table = tables[layer_name]
                edittypes = ET.Element("edittypes")
                editform = ET.Element("attributeEditorForm")

                layer.append(edittypes)
                layer.append(editform)

                columns_container = ET.Element("attributeEditorContainer")
                columns_container.attrib["name"] = "Columns"
                columns_container.attrib["columnCount"] = "1"
                relations_container = ET.Element("attributeEditorContainer")
                relations_container.attrib["name"] = "1:N Links"
                relations_container.attrib["columnCount"] = "1"
                backrelations_container = ET.Element("attributeEditorContainer")
                backrelations_container.attrib["name"] = "Back Links"
                backrelations_container.attrib["columnCount"] = "1"
                editform.append(columns_container)

                for idx, c in enumerate(table.columns()):
                    edittype = ET.Element("edittype")
                    edittype.attrib["widgetv2type"] = "TextEdit"
                    edittype.attrib["name"] = c.name()
                    wconfig = ET.Element("widgetv2config")
                    wconfig.attrib["IsMultiline"] = "0"
                    wconfig.attrib["fieldEditable"] = "0"
                    wconfig.attrib["UseHtml"] = "0"
                    wconfig.attrib["labelOnTop"] = "0"
                    edittype.append(wconfig)
                    edittypes.append(edittype)

                    field = ET.Element("attributeEditorField")
                    field.attrib["index"] = str(idx)
                    field.attrib["name"] = c.name()
                    columns_container.append(field)

                if simple_back_links.get(table.name()) is not None:
                    for sl in simple_back_links[table.name()]:
                        backrelation = ET.Element("attributeEditorRelation")
                        backrelation.attrib["relation"] = sl[0] + "_" + sl[1].name()
                        backrelation.attrib["name"] = sl[0] + "_" + sl[1].name()
                        backrelations_container.append(backrelation)

                for link in table.links():
                    if link.max_occurs() is None:
                        relation = ET.Element("attributeEditorRelation")
                        relation.attrib["relation"] = link.ref_table().name()
                        relation.attrib["name"] = link.name()
                        relations_container.append(relation)
                        continue
                    print("link to", link.ref_table().name(), "via", link.name())
                    edittype = ET.Element("edittype")
                    edittype.attrib["widgetv2type"] = "RelationReference"
                    edittype.attrib["name"] = link.name() + "_id"
                    wconfig = ET.Element("widgetv2config")
                    wconfig.attrib["OrderByValue"] = "0"
                    wconfig.attrib["fieldEditable"] = "0"
                    wconfig.attrib["ShowForm"] = "1" # embed the form
                    wconfig.attrib["Relation"] = table.name() + "_" + link.name()
                    wconfig.attrib["ReadOnly"] = "1"
                    # allow map selection tools ?
                    ref_layer = layers[link.ref_table().name()]
                    has_geometry = len(link.ref_table().geometries()) > 0
                    wconfig.attrib["MapIdentification"] = "1" if has_geometry else "0"
                    wconfig.attrib["labelOnTop"] = "0"
                    wconfig.attrib["AllowNULL"] = "1"
                    edittype.append(wconfig)
                    edittypes.append(edittype)

                    field = ET.Element("attributeEditorField")
                    field.attrib["index"] = str(idx)
                    field.attrib["name"] = link.name() + "_id"
                    columns_container.append(field)
                    idx += 1

                for link in table.back_links():
                    print("*** backlink to", link.ref_table().name(), "via", link.name())
                    edittype = ET.Element("edittype")
                    edittype.attrib["widgetv2type"] = "RelationReference"
                    edittype.attrib["name"] = link.ref_table().name() + "_id"
                    wconfig = ET.Element("widgetv2config")
                    wconfig.attrib["OrderByValue"] = "0"
                    wconfig.attrib["fieldEditable"] = "0"
                    wconfig.attrib["ShowForm"] = "0" # embed the form
                    wconfig.attrib["Relation"] = link.ref_table().name() + "_" + link.name()
                    wconfig.attrib["ReadOnly"] = "1"
                    # allow map selection tools ?
                    ref_layer = layers[link.ref_table().name()]
                    has_geometry = len(link.ref_table().geometries()) > 0
                    wconfig.attrib["MapIdentification"] = "1" if has_geometry else "0"
                    wconfig.attrib["labelOnTop"] = "0"
                    wconfig.attrib["AllowNULL"] = "1"
                    edittype.append(wconfig)
                    edittypes.append(edittype)

                    field = ET.Element("attributeEditorField")
                    field.attrib["index"] = str(idx)
                    field.attrib["name"] = link.ref_table().name() + "_id"
                    columns_container.append(field)
                    idx += 1

                if len(relations_container) > 0:
                    editform.append(relations_container)
                if len(backrelations_container) > 0:
                    editform.append(backrelations_container)

    fo = open(qgis_file, "w")
    fo.write(ET.tostring(root))
    fo.close()


