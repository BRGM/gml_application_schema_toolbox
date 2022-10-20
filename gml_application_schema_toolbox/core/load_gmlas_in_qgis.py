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

from typing import Union

from qgis.core import (
    QgsAttributeEditorContainer,
    QgsAttributeEditorField,
    QgsAttributeEditorRelation,
    QgsCoordinateReferenceSystem,
    QgsEditFormConfig,
    QgsEditorWidgetSetup,
    QgsMapLayerLegend,
    QgsProject,
    QgsProviderConnectionException,
    QgsProviderRegistry,
    QgsRelation,
    QgsSettings,
    QgsSimpleLegendNode,
    QgsVectorLayer,
    QgsVectorLayerJoinInfo,
)

from gml_application_schema_toolbox.__about__ import DIR_PLUGIN_ROOT
from gml_application_schema_toolbox.core.xml_utils import no_ns, no_prefix
from gml_application_schema_toolbox.gui.custom_viewers import get_custom_viewers
from gml_application_schema_toolbox.gui.qgis_form_custom_widget import (
    install_viewer_on_feature_form,
)
from gml_application_schema_toolbox.toolbelt.log_handler import PlgLogger


def _qgis_layer(
    uri,
    schema_name,
    layer_name,
    geometry_column,
    provider,
    qgis_layer_name,
    layer_xpath,
    layer_pkid,
):
    if geometry_column is not None:
        g_column = "({})".format(geometry_column)
    else:
        g_column = ""
    if provider in ("SQLite", "sqlite", "ogr"):
        # use OGR for spatialite loading
        couche = QgsVectorLayer(
            "{}|layername={}{}".format(uri, layer_name, g_column),
            qgis_layer_name,
            "ogr",
        )
        couche.setProviderEncoding("UTF-8")
    elif provider in ("spatialite"):
        # use OGR for spatialite loading
        couche = QgsVectorLayer(
            "{} table={} {}".format(uri, layer_name, g_column),
            qgis_layer_name,
            "spatialite",
        )
        couche.setProviderEncoding("UTF-8")
    else:
        if schema_name is not None:
            s_table = '"{}"."{}"'.format(schema_name, layer_name)
        else:
            s_table = '"{}"'.format(layer_name)
        couche = QgsVectorLayer(
            "{} table={} {} sql=".format(uri, s_table, g_column),
            qgis_layer_name,
            "postgres",
        )

    # sets xpath
    if layer_xpath:
        couche.setCustomProperty("xpath", layer_xpath)
    couche.setCustomProperty("pkid", layer_pkid)
    return couche


class CustomViewerLegend(QgsMapLayerLegend):
    def __init__(self, text, icon, parent=None):
        QgsMapLayerLegend.__init__(self, parent)
        self.text = text
        self.icon = icon

    def createLayerTreeModelLegendNodes(self, layer_tree_layer):
        return [QgsSimpleLegendNode(layer_tree_layer, self.text, self.icon, self)]


def import_in_qgis(
    gmlas_uri: str,
    provider: str,
    auto_join: bool,
    add_form_code: bool,
    schema: Union[str, None] = None,
):
    """Imports layers from a GMLAS file in QGIS with relations and editor widgets

    @param gmlas_uri connection parameters
    @param provider name of the QGIS provider that handles gmlas_uri parameters
    @param add_form_code set this to true to load the custom form code
    @param schema name of the PostgreSQL schema where tables and metadata tables are
    """
    PlgLogger.log(
        message=f"Start importing {gmlas_uri} (provider: {provider}) into QGIS",
        log_level=4,
    )

    # set provider to ogr only for SQLite
    if provider in ("sqlite", "SQLite"):
        provider = "ogr"

    if schema is not None:
        schema_s = schema + "."
    else:
        schema_s = ""

    md = QgsProviderRegistry.instance().providerMetadata(provider)
    conn = md.createConnection(gmlas_uri, {})
    PlgLogger.log(message=f"DEBUG Connect to {conn.uri()}", log_level=4)

    # get list of layers
    layers_attrs = {
        "layer_name": 0,
        "layer_xpath": 1,
        "layer_category": 2,
        "layer_pkid_name": 3,
        "layer_parent_pkid_name": 4,
        "f_geometry_column": 5,
        "srid": 6,
    }
    sql = f"select o.layer_name, o.layer_xpath, o.layer_category, o.layer_pkid_name, o.layer_parent_pkid_name, g.f_geometry_column, g.srid from {schema_s}_ogr_layers_metadata o left join geometry_columns g on g.f_table_name = o.layer_name"
    PlgLogger.log(message=f"DEBUG Get list of layers with query : {sql}", log_level=4)

    result = []
    try:
        result = conn.executeSql(sql)
        PlgLogger.log(message=f"DEBUG List of layers : {result}", log_level=4)
    except QgsProviderConnectionException as err:
        PlgLogger.log(message=err, log_level=2, push=True)

    layers = {}
    for f in result:
        ln = f[layers_attrs["layer_name"]]
        if ln not in layers:
            layers[ln] = {
                "uid": f[layers_attrs["layer_pkid_name"]],
                "category": f[layers_attrs["layer_category"]],
                "xpath": f[layers_attrs["layer_xpath"]],
                "parent_pkid": f[layers_attrs["layer_parent_pkid_name"]],
                "srid": f[layers_attrs["srid"]],
                "geometry_column": f[layers_attrs["f_geometry_column"]],
                "1_n": [],  # 1:N relations
                "layer_id": None,
                "layer_name": ln,
                "layer": None,
                "fields": [],
            }
        else:
            # additional geometry columns
            g = f[layers_attrs["f_geometry_column"]]
            k = "{} ({})".format(ln, g)
            layers[k] = dict(layers[ln])
            layers[k]["geometry_column"] = g

    # collect fields with xlink:href
    fields_attrs = {"field_name": 0, "field_xpath": 1}
    href_fields = {}
    for ln, layer in layers.items():
        layer_name = layer["layer_name"]
        sql = f"select field_name, field_xpath from {schema_s}_ogr_fields_metadata where layer_name='{layer_name}'"
        PlgLogger.log(
            message=f"DEBUG Get fields of layer {layer_name} with query : {sql}",
            log_level=4,
        )
        try:
            result = conn.executeSql(sql)
        except QgsProviderConnectionException as err:
            PlgLogger.log(message=err, log_level=2, push=True)
        PlgLogger.log(message=f"DEBUG List of fields : {result}", log_level=4)
        for f in result:
            field_name, field_xpath = (
                f[fields_attrs["field_name"]],
                f[fields_attrs["field_xpath"]],
            )
            if field_xpath and field_xpath.endswith("@xlink:href"):
                if ln not in href_fields:
                    href_fields[ln] = []
                href_fields[ln].append(field_name)

    # with unknown srid, don't ask for each layer, set to a default
    settings = QgsSettings()
    projection_behavior = settings.value("Projections/defaultBehavior")
    projection_default = settings.value("Projections/layerDefaultCrs")
    settings.setValue("Projections/defaultBehavior", "useGlobal")
    settings.setValue("Projections/layerDefaultCrs", "EPSG:4326")

    # add layers
    crs = QgsCoordinateReferenceSystem("EPSG:4326")
    for ln in sorted(layers.keys()):
        lyr = layers[ln]
        g_column = lyr["geometry_column"] or None
        PlgLogger.log(
            message=f"DEBUG Load layer with uri={gmlas_uri}, schema={schema}, layer={lyr['layer_name']}, geometry={g_column}, \
            provider={provider}, ln={ln}, xpath={lyr['xpath']}, uid={lyr['uid']}"
        )
        couches = _qgis_layer(
            gmlas_uri,
            schema,
            lyr["layer_name"],
            g_column,
            provider,
            ln,
            lyr["xpath"],
            lyr["uid"],
        )
        # if not couches.isValid():
        #     raise RuntimeError(
        #         "Problem loading layer {} with {}".format(ln, couches.source())
        #     )
        if g_column is not None:
            if lyr["srid"]:
                crs = QgsCoordinateReferenceSystem("EPSG:{}".format(lyr["srid"]))
            couches.setCrs(crs)
        QgsProject.instance().addMapLayer(couches)
        layers[ln]["layer_id"] = couches.id()
        layers[ln]["layer"] = couches
        # save fields which represent a xlink:href
        if ln in href_fields:
            couches.setCustomProperty("href_fields", href_fields[ln])
        # save gmlas_uri
        couches.setCustomProperty("ogr_uri", gmlas_uri)
        couches.setCustomProperty("ogr_schema", schema)

        # change icon the layer has a custom viewer
        xpath = no_ns(couches.customProperty("xpath", ""))
        for viewer_cls, _ in get_custom_viewers().values():
            tag = no_prefix(viewer_cls.xml_tag())
            if tag == xpath:
                lg = CustomViewerLegend(viewer_cls.name(), viewer_cls.icon())
                couches.setLegend(lg)

    # restore settings
    settings.setValue("Projections/defaultBehavior", projection_behavior)
    settings.setValue("Projections/layerDefaultCrs", projection_default)

    # add 1:1 relations
    relations_1_1_attrs = {
        "layer_name": 0,
        "field_name": 1,
        "field_related_layer": 2,
        "child_pkid": 3,
    }
    relations_1_1 = []
    with open(DIR_PLUGIN_ROOT / "sql/get_1_1_relations.sql", "r") as f:
        sql = f.read().format(schema=schema_s)

    PlgLogger.log(message=f"DEBUG Add relations 1:1 with query : {sql}", log_level=4)
    try:
        result = conn.executeSql(sql)
    except QgsProviderConnectionException as err:
        PlgLogger.log(message=err, log_level=2, push=True)
    PlgLogger.log(message=f"DEBUG Relations 1:1 : {result}", log_level=4)
    if result is not None:
        for f in result:
            rel = QgsRelation()
            rel.setId(
                "1_1_"
                + f[relations_1_1_attrs["layer_name"]]
                + "_"
                + f[relations_1_1_attrs["field_name"]]
            )
            rel.setName(
                "1_1_"
                + f[relations_1_1_attrs["layer_name"]]
                + "_"
                + f[relations_1_1_attrs["field_name"]]
            )
            # parent layer
            rel.setReferencingLayer(
                layers[f[relations_1_1_attrs["layer_name"]]]["layer_id"]
            )
            # child layer
            rel.setReferencedLayer(
                layers[f[relations_1_1_attrs["field_related_layer"]]]["layer_id"]
            )
            # parent, child
            rel.addFieldPair(
                f[relations_1_1_attrs["field_name"]],
                f[relations_1_1_attrs["child_pkid"]],
            )
            if rel.isValid():
                relations_1_1.append(rel)

    # add 1:N relations
    relations_1_n_attrs = {
        "layer_name": 0,
        "parent_pkid": 1,
        "child_layer": 2,
        "child_pkid": 3,
    }
    relations_1_n = []
    with open(DIR_PLUGIN_ROOT / "sql/get_1_n_relations.sql", "r") as f:
        sql = f.read().format(schema=schema_s)

    PlgLogger.log(message=f"DEBUG Add relations 1:N with query : {sql}", log_level=4)
    try:
        result = conn.executeSql(sql)
    except QgsProviderConnectionException as err:
        PlgLogger.log(message=err, log_level=2, push=True)
    PlgLogger.log(message=f"DEBUG Relations 1:N : {result}", log_level=4)

    if result is not None:
        for f in result:
            parent_layer = f[relations_1_n_attrs["layer_name"]]
            child_layer = f[relations_1_n_attrs["child_layer"]]
            if parent_layer not in layers or child_layer not in layers:
                continue
            rel = QgsRelation()
            rel.setId(
                "1_n_"
                + f[relations_1_n_attrs["layer_name"]]
                + "_"
                + f[relations_1_n_attrs["child_layer"]]
                + "_"
                + f[relations_1_n_attrs["parent_pkid"]]
                + "_"
                + f[relations_1_n_attrs["child_pkid"]]
            )
            rel.setName(f[relations_1_n_attrs["child_layer"]])
            # parent layer
            rel.setReferencedLayer(layers[parent_layer]["layer_id"])
            # child layer
            rel.setReferencingLayer(layers[child_layer]["layer_id"])
            # parent, child
            rel.addFieldPair(
                f[relations_1_n_attrs["child_pkid"]],
                f[relations_1_n_attrs["parent_pkid"]],
            )
            if rel.isValid():
                relations_1_n.append(rel)
                # add relation to layer
                layers[f[relations_1_n_attrs["layer_name"]]]["1_n"].append(rel)

    for rel in relations_1_1 + relations_1_n:
        QgsProject.instance().relationManager().addRelation(rel)

    # add "show form" option to 1:1 relations
    for rel in relations_1_1:
        couches = rel.referencingLayer()
        idx = rel.referencingFields()[0]
        s = QgsEditorWidgetSetup(
            "RelationReference",
            {
                "AllowNULL": False,
                "ReadOnly": True,
                "Relation": rel.id(),
                "OrderByValue": False,
                "MapIdentification": False,
                "AllowAddFeatures": False,
                "ShowForm": True,
            },
        )
        couches.setEditorWidgetSetup(idx, s)

    # auto join 1:1 relations
    if auto_join:
        if len(relations_1_1) == 0:
            PlgLogger.log(message="there are no 1:1 relations to auto join")
        else:
            for rel in relations_1_1:
                target_field, join_field = list(rel.fieldPairs().items())[0]
                join_object = QgsVectorLayerJoinInfo()
                join_object.setJoinLayerId(rel.referencedLayerId())
                join_object.setJoinLayer(rel.referencedLayer())
                join_object.setJoinFieldName(join_field)
                join_object.setTargetFieldName(target_field)
                join_object.setUsingMemoryCache(True)

                parent_layer = QgsProject.instance().mapLayers()[
                    rel.referencingLayerId()
                ]
                parent_layer.addJoin(join_object)
                PlgLogger.log(message="joined layer {parent_layer}")

    # setup form for layers
    for layer, lyr in layers.items():
        couche = lyr["layer"]
        fc = couche.editFormConfig()
        fc.clearTabs()
        fc.setLayout(QgsEditFormConfig.TabLayout)
        # Add fields
        c = QgsAttributeEditorContainer("Main", fc.invisibleRootContainer())
        c.setIsGroupBox(False)  # a tab
        for idx, f in enumerate(couche.fields()):
            c.addChildElement(QgsAttributeEditorField(f.name(), idx, c))
        fc.addTab(c)

        # Add 1:N relations
        c_1_n = QgsAttributeEditorContainer("1:N links", fc.invisibleRootContainer())
        c_1_n.setIsGroupBox(False)  # a tab
        fc.addTab(c_1_n)

        for rel in lyr["1_n"]:
            c_1_n.addChildElement(QgsAttributeEditorRelation(rel.name(), rel, c_1_n))

        couche.setEditFormConfig(fc)
        
        if add_form_code:
            install_viewer_on_feature_form(couche)
