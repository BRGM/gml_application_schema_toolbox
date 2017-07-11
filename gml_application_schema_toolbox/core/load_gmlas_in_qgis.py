# -*- coding: utf-8 -*-

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

from qgis.core import QgsVectorLayer, QgsProject, QgsCoordinateReferenceSystem, QgsRelation, QgsEditorWidgetSetup
from qgis.core import QgsEditFormConfig, QgsAttributeEditorField, QgsAttributeEditorRelation, QgsAttributeEditorContainer
from qgis.PyQt.QtCore import QVariant

def import_in_qgis(gmlas_uri, provider, schema = None):
    """Imports layers from a GMLAS file in QGIS with relations and editor widgets

    @param gmlas_uri connection parameters
    @param provider name of the QGIS provider that handles gmlas_uri parameters (postgresql or spatialite)
    """
    if schema is not None:
        schema_s = schema + "."
    else:
        schema_s = ""
        
    # get list of layers
    sql = "select o.*, g.f_geometry_column, g.srid from {}_ogr_layers_metadata o left join geometry_columns g on g.f_table_name = o.layer_name".format(schema_s)
    if provider == "postgres":
        sql = sql.replace("f_geometry_column", "f_geometry_column::text")
        sql = "select row_number() over () as _uid_, * from ({}) _r".format(sql)
    l = QgsVectorLayer(gmlas_uri + ' key=\'_uid_\' table="(' + sql + ')" sql=', "l", provider)
    if not l.isValid():
        raise RuntimeError("Cannot find layers metadata")
    layers = dict([(f.attribute("layer_name"),
                    {'uid': f.attribute("layer_pkid_name"),
                     'category': f.attribute("layer_category"),
                     'xpath': f.attribute("layer_xpath"),
                     'parent_pkid': f.attribute("layer_parent_pkid_name"),
                     'geometry_column': f.attribute("f_geometry_column"),
                     'srid': f.attribute("srid"),
                     '1_n' : [], # 1:N relations
                     'layer_id': None,
                     'layer': None,
                     'fields' : []}) for f in l.getFeatures()])

    crs = QgsCoordinateReferenceSystem("EPSG:4326")
    for ln in sorted(layers.keys()):
        lyr = layers[ln]
        g_column = lyr["geometry_column"]
        if schema is None:
            table_name = '"{}"'.format(ln)
        else:
            table_name = '"{}"."{}"'.format(schema, ln)
        if not (isinstance(g_column, QVariant) and g_column.isNull()):
            l = QgsVectorLayer(gmlas_uri + ' table={} ({}) sql='.format(table_name, g_column), ln, provider)
        else:
            l = QgsVectorLayer(gmlas_uri + ' table={} sql='.format(table_name), ln, provider)
        if not l.isValid():
            raise RuntimeError("Problem loading layer {}".format(ln))
        if lyr["srid"]:
            crs = QgsCoordinateReferenceSystem("EPSG:{}".format(lyr["srid"]))
        l.setCrs(crs)
        QgsProject.instance().addMapLayer(l)
        layers[ln]['layer_id'] = l.id()
        layers[ln]['layer'] = l

    # add 1:1 relations
    relations_1_1 = []
    sql = """
select
  layer_name, field_name, field_related_layer, r.child_pkid
from
  {}_ogr_fields_metadata f
  join {}_ogr_layer_relationships r
    on r.parent_layer = f.layer_name
   and r.parent_element_name = f.field_name
where
  field_category in ('PATH_TO_CHILD_ELEMENT_WITH_LINK', 'PATH_TO_CHILD_ELEMENT_NO_LINK')
  and field_max_occurs=1
""".format(schema_s, schema_s)
    if provider == "postgres":
        sql = "select row_number() over () as _uid_, * from ({}) _r".format(sql)
    l = QgsVectorLayer(gmlas_uri + ' key=\'_uid_\' table="(' + sql + ')" sql=', "l", provider)
    if not l.isValid():
        raise RuntimeError("SQL error when requesting 1:1 relations")
    for f in l.getFeatures():
        rel = QgsRelation()
        rel.setId('1_1_' + f['layer_name'] + '_' + f['field_name'])
        rel.setName('1_1_' + f['layer_name'] + '_' + f['field_name'])
        # parent layer
        rel.setReferencingLayer(layers[f['layer_name']]['layer_id'])
        # child layer
        rel.setReferencedLayer(layers[f['field_related_layer']]['layer_id'])
        # parent, child
        rel.addFieldPair(f['field_name'], f['child_pkid'])
        #rel.generateId()
        if rel.isValid():
            relations_1_1.append(rel)

    # add 1:N relations
    relations_1_n = []
    sql = """
select
  layer_name, r.parent_pkid, field_related_layer, r.child_pkid
from
  {}_ogr_fields_metadata f
  join {}_ogr_layer_relationships r
    on r.parent_layer = f.layer_name
   and r.child_layer = f.field_related_layer
where
  field_category in ('PATH_TO_CHILD_ELEMENT_WITH_LINK', 'PATH_TO_CHILD_ELEMENT_NO_LINK')
  and field_max_occurs>1
""".format(schema_s, schema_s)
    if provider == "postgres":
        sql = "select row_number() over () as _uid_, * from ({}) _r".format(sql)
    l = QgsVectorLayer(gmlas_uri + ' key=\'_uid_\' table="(' + sql + ')" sql=', "l", provider)
    if not l.isValid():
        raise RuntimeError("SQL error when requesting 1:n relations")
    for f in l.getFeatures():
        rel = QgsRelation()
        rel.setId('1_n_' + f['layer_name'] + '_' + f['field_related_layer'] + '_' + f['parent_pkid'] + '_' + f['child_pkid'])
        rel.setName(f['field_related_layer'])
        # parent layer
        rel.setReferencedLayer(layers[f['layer_name']]['layer_id'])
        # child layer
        rel.setReferencingLayer(layers[f['field_related_layer']]['layer_id'])
        # parent, child
        rel.addFieldPair(f['child_pkid'], f['parent_pkid'])
        #rel.addFieldPair(f['child_pkid'], 'ogc_fid')
        if rel.isValid():
            relations_1_n.append(rel)
            # add relation to layer
            layers[f['layer_name']]['1_n'].append(rel)
            
    QgsProject.instance().relationManager().setRelations(relations_1_1 + relations_1_n)

    # add "show form" option to 1:1 relations
    for rel in relations_1_1:
        l = rel.referencingLayer()
        idx = rel.referencingFields()[0]
        s = QgsEditorWidgetSetup("RelationReference", {'AllowNULL': False,
                                      'ReadOnly': True,
                                      'Relation': rel.id(),
                                      'OrderByValue': False,
                                      'MapIdentification': False,
                                      'AllowAddFeatures': False,
                                      'ShowForm': True})
        l.setEditorWidgetSetup(idx, s)

    # setup form for layers
    for layer, lyr in layers.items():
        l = lyr['layer']
        fc = l.editFormConfig()
        fc.clearTabs()
        fc.setLayout(QgsEditFormConfig.TabLayout)
        # Add fields
        c = QgsAttributeEditorContainer("Main", fc.invisibleRootContainer())
        c.setIsGroupBox(False) # a tab
        for idx, f in enumerate(l.fields()):
            c.addChildElement(QgsAttributeEditorField(f.name(), idx, c))
        fc.addTab(c)

        # Add 1:N relations
        c_1_n = QgsAttributeEditorContainer("1:N links", fc.invisibleRootContainer())
        c_1_n.setIsGroupBox(False) # a tab
        fc.addTab(c_1_n)
        
        for rel in lyr['1_n']:
            c_1_n.addChildElement(QgsAttributeEditorRelation(rel.name(), rel, c_1_n))

        l.setEditFormConfig(fc)

