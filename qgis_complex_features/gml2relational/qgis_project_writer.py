from __future__ import print_function
import logging
import sys

import xml.etree.ElementTree as ET

import pyspatialite.dbapi2 as db

app = None

def XMLNode(tag, attrib = {}, text = None):
    elt = ET.Element(tag, attrib)
    if text is not None:
        elt.text = text
    return elt

def to_pretty_xml(node, level = 0):
    e = [node.tag]
    e += ['{}="{}"'.format(an, av) for an, av in node.attrib.iteritems()]
    l = "  " * level + "<" + " ".join(e)
    if len(node) == 0:
        if node.text is None:
            yield l + "/>"
        else:
            yield l + ">" + node.text + "</{}>".format(node.tag)
    else:
        yield l + ">" + (node.text if node.text is not None else "")
        for child in node:
            for s in to_pretty_xml(child, level+1):
                yield s
        yield "  " * level + "</{}>".format(node.tag)
        

def create_qgis_project_from_model(model, sqlite_file, qgis_file, srs_db_file, qgis_version = "2.14"):
    tables = model.tables()
    tables_rows = model.tables_rows()
    root_name = model.root_name()

    # QGIS layers must have an ID that is at least 17 letters wide
    import datetime
    id_suffix = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "001"

    layers_xml = {}
    main_group_xml = XMLNode('layer-tree-group', {'checked' : 'Qt::Checked', 'expanded' : '1'})
    group_xml = ET.SubElement(main_group_xml, 'layer-tree-group', {'name': root_name, 'expanded' : '1'})
    child_group_xml = ET.SubElement(group_xml, 'layer-tree-group', {'name': u'linked tables', 'expanded' : '0'})
    geom_group_xml = XMLNode('layer-tree-group', {'name': u"geometries", 'expanded' : '1', 'checked' : 'Qt::Checked'})
    project_xml = XMLNode('qgis', {'version' : qgis_version })
    relations_xml = XMLNode('relations')
    project_xml.extend([main_group_xml, relations_xml])

    srs_conn = db.connect(srs_db_file)
    srs_cur = srs_conn.cursor()

    # load a layer for each table
    for table_name, table in tables.iteritems():
        geometry = table.geometries()[0].name() if len(table.geometries()) > 0 else None
        geometry_type = table.geometries()[0].type() if len(table.geometries()) > 0 else None
        src = "dbname='{}' table=\"{}\"{} sql=".format(sqlite_file, table.name(), " (" + geometry + ")" if geometry is not None else "")

        layer_xml = XMLNode('maplayer', {'geometry' : 'No geometry' if geometry_type is None else geometry_type, 'type' : 'vector'})
        layer_xml.extend([XMLNode('id', text = table_name + id_suffix), 
                          XMLNode('datasource', text = src),
                          XMLNode('shortname', text = table_name),
                          XMLNode('layername', text = table_name),
                          XMLNode('provider', {'encoding' : 'System'}, text = 'spatialite')])

        if geometry is not None:
            srs_xml = XMLNode("srs")
            x = ET.SubElement(srs_xml, "spatialrefsys")
            cur = srs_conn.execute("SELECT srs_id, description, projection_acronym, ellipsoid_acronym, parameters, srid, auth_name, auth_id, is_geo " +
                                   "FROM tbl_srs WHERE srid=?", (table.geometries()[0].srid(),))
            r = cur.fetchone()
            if r is not None:
                srs_id, description, project_acronym, ellipsoid_acronym, parameters, srid, auth_name, auth_id, is_geo = r
                x.append(XMLNode("proj4", text = parameters))
                x.append(XMLNode("srsid", text = str(srs_id)))
                x.append(XMLNode("authid", text = "{}:{}".format(auth_name,auth_id)))
                x.append(XMLNode("description", text = description))
                x.append(XMLNode("projectionacronym", text = project_acronym))
                x.append(XMLNode("ellispoidacronym", text = ellipsoid_acronym))
                x.append(XMLNode("geographicflag", text = "1" if is_geo else "0"))
                layer_xml.append(srs_xml)
            else:
                logging.warning("SRID {} not found !".format(table.geometries()[0].srid()))
        
        layers_xml[table_name] = layer_xml
        
        l_xml = XMLNode('layer-tree-layer', {'checked' : 'Qt::Checked', 'expanded' : '1', 'name' : table_name, 'id' : table_name + id_suffix})
        if table_name == root_name:
            group_xml.insert(0, l_xml)
        elif geometry is not None:
            geom_group_xml.append(l_xml)
        else:
            child_group_xml.append(l_xml)
        
    # declare relations
    for table_name, table in tables.iteritems():
        for link in table.links():
            if link.max_occurs() is None:
                continue

            referencingField = link.name() + "_id"
            referencedField = "id"
            rel_xml = XMLNode("relation", {'id' : table.name() + '_' + link.name(),
                                              'name' : table.name() +'_' + link.name(),
                                              'referencedLayer' : link.ref_table().name() + id_suffix,
                                              'referencingLayer' : table.name() + id_suffix})
            field_xml = ET.SubElement(rel_xml, "fieldRef", {'referencedField' : referencedField, 'referencingField' : referencingField})
            relations_xml.append(rel_xml)

        for bl in table.back_links():
            # create a relation for this backlink
            referencingField = bl.ref_table().name() + u"_id"
            referencedField = "id"
            rel_xml = XMLNode("relation", {'id' : table.name(),
                                              'name' : table.name(),
                                              'referencedLayer' : bl.ref_table().name() + id_suffix,
                                              'referencingLayer' : table.name() + id_suffix})
            field_xml = ET.SubElement(rel_xml, "fieldRef", {'referencedField' : referencedField, 'referencingField' : referencingField})
            relations_xml.append(rel_xml)

    project_xml.extend(layers_xml.values())
    if len(geom_group_xml) > 0:
        group_xml.append(geom_group_xml)

    simple_back_links = {}
    for table_name, table in tables.iteritems():
        for link in table.links():
            if link.max_occurs() == 1:
                dest_table = link.ref_table().name()
                simple_back_links[dest_table] = (simple_back_links.get(dest_table) or []) + [(table_name, link)]

    for table_name, table in tables.iteritems():
        layer = layers_xml[table_name]
        #raw_input()
        edittypes = XMLNode("edittypes")
        editform = XMLNode("attributeEditorForm")

        layer.append(XMLNode("editorlayout", text = "tablayout"))
        layer.append(edittypes)
        layer.append(editform)

        columns_container = XMLNode("attributeEditorContainer", {"name": "Columns", "columnCount": "1"})
        relations_container = XMLNode("attributeEditorContainer", {"name": "1:N Links", "columnCount": "1"})
        backrelations_container = XMLNode("attributeEditorContainer", {"name": "Back Links", "columnCount": "1"})
        editform.append(columns_container)

        for idx, c in enumerate(table.columns()):
            edittype = XMLNode("edittype")
            edittype.attrib["widgetv2type"] = "TextEdit"
            edittype.attrib["name"] = c.name()
            wconfig = XMLNode("widgetv2config")
            wconfig.attrib["IsMultiline"] = "0"
            wconfig.attrib["fieldEditable"] = "0"
            wconfig.attrib["UseHtml"] = "0"
            wconfig.attrib["labelOnTop"] = "0"
            edittype.append(wconfig)
            edittypes.append(edittype)

            field = XMLNode("attributeEditorField")
            field.attrib["index"] = str(idx)
            field.attrib["name"] = c.name()
            columns_container.append(field)

        if simple_back_links.get(table.name()) is not None:
            for sl in simple_back_links[table.name()]:
                backrelation = XMLNode("attributeEditorRelation")
                backrelation.attrib["relation"] = sl[0] + "_" + sl[1].name()
                backrelation.attrib["name"] = sl[0] + "_" + sl[1].name()
                backrelations_container.append(backrelation)

        for link in table.links():
            if link.max_occurs() is None:
                relation = XMLNode("attributeEditorRelation")
                relation.attrib["relation"] = link.ref_table().name()
                relation.attrib["name"] = link.name()
                relations_container.append(relation)
                continue
            edittype = XMLNode("edittype")
            edittype.attrib["widgetv2type"] = "RelationReference"
            edittype.attrib["name"] = link.name() + "_id"
            wconfig = XMLNode("widgetv2config")
            wconfig.attrib["OrderByValue"] = "0"
            wconfig.attrib["fieldEditable"] = "0"
            wconfig.attrib["ShowForm"] = "1" # embed the form
            wconfig.attrib["Relation"] = table.name() + "_" + link.name()
            wconfig.attrib["ReadOnly"] = "1"
            # allow map selection tools ?
            has_geometry = len(link.ref_table().geometries()) > 0
            wconfig.attrib["MapIdentification"] = "1" if has_geometry else "0"
            wconfig.attrib["labelOnTop"] = "0"
            wconfig.attrib["AllowNULL"] = "1"
            edittype.append(wconfig)
            edittypes.append(edittype)

            field = XMLNode("attributeEditorField")
            field.attrib["index"] = str(idx)
            field.attrib["name"] = link.name() + "_id"
            columns_container.append(field)
            idx += 1

        for link in table.back_links():
            edittype = XMLNode("edittype")
            edittype.attrib["widgetv2type"] = "RelationReference"
            edittype.attrib["name"] = link.ref_table().name() + "_id"
            wconfig = XMLNode("widgetv2config")
            wconfig.attrib["OrderByValue"] = "0"
            wconfig.attrib["fieldEditable"] = "0"
            wconfig.attrib["ShowForm"] = "0" # embed the form
            wconfig.attrib["Relation"] = link.ref_table().name() + "_" + link.name()
            wconfig.attrib["ReadOnly"] = "1"
            # allow map selection tools ?
            has_geometry = len(link.ref_table().geometries()) > 0
            wconfig.attrib["MapIdentification"] = "1" if has_geometry else "0"
            wconfig.attrib["labelOnTop"] = "0"
            wconfig.attrib["AllowNULL"] = "1"
            edittype.append(wconfig)
            edittypes.append(edittype)

            field = XMLNode("attributeEditorField")
            field.attrib["index"] = str(idx)
            field.attrib["name"] = link.ref_table().name() + "_id"
            columns_container.append(field)
            idx += 1

        if len(relations_container) > 0:
            editform.append(relations_container)
        if len(backrelations_container) > 0:
            editform.append(backrelations_container)

    fo = open(qgis_file, "w")
    for line in to_pretty_xml(project_xml):
        fo.write(line + "\n")
    fo.close()


