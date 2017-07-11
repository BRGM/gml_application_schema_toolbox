from osgeo import ogr

def fix_geometry_types_in_spatialite(file_path):
    """
       Fixes geometry_columns table with the correct geometry type of each layer
       It assumes each layer has a unique geometry type
    """
    driver = ogr.GetDriverByName("sqlite")
    ds = ogr.Open(file_path, 1)
    l = ds.ExecuteSQL("select * from geometry_columns where geometry_type = 0")
    layers = [(r.GetField('f_table_name'), r.GetField('f_geometry_column')) for r in l]
    print("****", layers)

    sql="""
update geometry_columns
set geometry_type = (select distinct
                            case when st_geometrytype({1})='POINT' then 1
                                 when st_geometrytype({1})='LINESTRING' then 2
                                 when st_geometrytype({1})='POLYGON' then 3
                            end
                     from {0} )
where
  f_table_name = '{0}'"""
    for ln, column in layers:
        ds.ExecuteSQL(sql.format(ln, column))
