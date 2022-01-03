select
  layer_name, field_name, field_related_layer, r.child_pkid
from
  {schema}_ogr_fields_metadata f
  join {schema}_ogr_layer_relationships r
    on r.parent_layer = f.layer_name
   and r.parent_element_name = f.field_name
where
  field_category in ('PATH_TO_CHILD_ELEMENT_WITH_LINK', 'PATH_TO_CHILD_ELEMENT_NO_LINK')
  and field_max_occurs=1
