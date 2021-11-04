SELECT
    _ogr_fields_metadata.layer_name,
    _ogr_fields_metadata.field_name,
    _ogr_layer_relationships.child_layer,
    _ogr_layer_relationships.child_pkid

FROM "{schema}"._ogr_fields_metadata

INNER JOIN "{schema}"._ogr_layer_relationships
    ON _ogr_layer_relationships.parent_element_name = _ogr_fields_metadata.field_name
    AND _ogr_layer_relationships.parent_layer = _ogr_fields_metadata.layer_name
    AND _ogr_layer_relationships.child_layer = _ogr_fields_metadata.field_related_layer

-- Filter by existing columns in current schema
INNER JOIN information_schema.columns
    ON  columns.table_schema = '{schema}'
    AND columns.table_name = _ogr_fields_metadata.layer_name
    AND columns.column_name = _ogr_fields_metadata.field_name

INNER JOIN information_schema.columns referenced_columns
    ON  referenced_columns.table_schema = '{schema}'
    AND referenced_columns.table_name = _ogr_layer_relationships.child_layer
    AND referenced_columns.column_name = _ogr_layer_relationships.child_pkid

WHERE field_category IN (
    'PATH_TO_CHILD_ELEMENT_NO_LINK',
    'PATH_TO_CHILD_ELEMENT_WITH_LINK');
