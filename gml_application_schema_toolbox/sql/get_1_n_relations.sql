select
  layer_name, r.parent_pkid, field_related_layer as child_layer, r.child_pkid
from
  {schema}_ogr_fields_metadata f
  join {schema}_ogr_layer_relationships r
    on r.parent_layer = f.layer_name
   and r.child_layer = f.field_related_layer
where
  field_category in ('PATH_TO_CHILD_ELEMENT_WITH_LINK', 'PATH_TO_CHILD_ELEMENT_NO_LINK')
  and field_max_occurs>1
-- junctions - 1st way
union all
select
  layer_name, r.parent_pkid, field_junction_layer as child_layer, 'parent_pkid' as child_pkid
from
  {schema}_ogr_fields_metadata f
  join {schema}_ogr_layer_relationships r
    on r.parent_layer = f.layer_name
   and r.child_layer = f.field_related_layer
where
  field_category = 'PATH_TO_CHILD_ELEMENT_WITH_JUNCTION_TABLE'
-- junctions - 2nd way
union all
select
  field_related_layer as layer_name, r.child_pkid, field_junction_layer as child_layer, 'child_pkid' as child_pkid
from
  {schema}_ogr_fields_metadata f
  join {schema}_ogr_layer_relationships r
    on r.parent_layer = f.layer_name
   and r.child_layer = f.field_related_layer
where
  field_category = 'PATH_TO_CHILD_ELEMENT_WITH_JUNCTION_TABLE'
