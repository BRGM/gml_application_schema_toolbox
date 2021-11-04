SELECT
    _ogr_fields_metadata.field_junction_layer,
    _ogr_layer_relationships.parent_layer,
    _ogr_layer_relationships.parent_pkid,
    _ogr_layer_relationships.child_layer,
    _ogr_layer_relationships.child_pkid

FROM "{schema}"._ogr_fields_metadata

LEFT JOIN "{schema}"._ogr_layer_relationships
    ON _ogr_layer_relationships.parent_element_name = _ogr_fields_metadata.field_name
    AND _ogr_layer_relationships.parent_layer = _ogr_fields_metadata.layer_name

-- Filter by existing columns in current schema
INNER JOIN information_schema.tables
    ON tables.table_schema = '{schema}'
    AND tables.table_name = _ogr_fields_metadata.field_junction_layer

WHERE field_category = 'PATH_TO_CHILD_ELEMENT_WITH_JUNCTION_TABLE';
