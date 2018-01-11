from osgeo import ogr
from .xml_utils import no_ns

def lstartswith(l1, l2):
    """Return True if l1 starts with elements in l2"""
    return len([(a,b) for (a,b) in zip(l1,l2) if a==b]) == len(l2)

class GmlAsXPathResolver:
    def __init__(self, uri, provider, schema):
        """
        @param gmlas_uri connection parameters
        @param provider name of the OGR provider that handles gmlas_uri parameters (PostgreSQL or SQLite)
        @param schema name of the PostgreSQL schema where tables and metadata tables are
        """
        
        ogr.UseExceptions()
        drv = ogr.GetDriverByName(provider)
        self._ds = drv.Open(uri)
        if self._ds is None:
            raise RuntimeError("Problem opening {}".format(uri))
        if schema != "":
            self._schema = schema + "."
        else:
            self._schema = ""

    def resolve_xpath(self, ogr_layer_name, ogr_layer_pkid_name, pkid_value, xpath):
        """Resolve an XPath relative to a current layer
        @param ogr_layer_name the name of the OGR layer
        @param the XPath relative to the layer
        @return the corresponding value(s) after xpath resolution
        """

        sql_field = ""
        sql_tables = []
        sql_joins = []
        sql_wheres = [((ogr_layer_name, ogr_layer_pkid_name), "'{}'".format(pkid_value))]

        lxpath = xpath.split('/')

        while lxpath != [] and lxpath != ["text()"]:
            layer_xpath = None
            for f in self._ds.ExecuteSQL("select layer_xpath from {}_ogr_layers_metadata where layer_name='{}'".format(self._schema, ogr_layer_name)):
                layer_xpath = f.GetField("layer_xpath").split('/')
            if layer_xpath is None:
                raise RuntimeError("Cannot find metadata of the layer '{}'".format(ogr_layer_name))

            #print("**************")
            #print("layer", ogr_layer_name, "pkid", ogr_layer_pkid_name)
            #print("xpath", lxpath)
            #print("layer_xpath", layer_xpath)

            # look for xpath of fields
            field_name = None
            field_category = None
            field_max_occurs = 0
            for f in self._ds.ExecuteSQL("""
select field_xpath, field_name, field_category, field_max_occurs
from {}_ogr_fields_metadata
where layer_name='{}'""".format(self._schema, ogr_layer_name)):
                field_xpath = f.GetField("field_xpath").split('/')
                #print("field_xpath", field_xpath)
                if lstartswith(field_xpath, layer_xpath):
                    # remove the layer_xpath
                    field_xpath = field_xpath[len(layer_xpath):]
                    #print("field_xpath2", [no_ns(x) for x in field_xpath])
                    if lstartswith(lxpath, [no_ns(x) for x in field_xpath]):
                        field_name = f.GetField("field_name")
                        field_category = f.GetField("field_category")
                        field_max_occurs = f.GetField("field_max_occurs")
                        #print("field_name =>", field_name, field_category, field_max_occurs)
                        # remaining xpath
                        lxpath = lxpath[len(field_xpath):]
                        break

            if field_name is None:
                # cannot find the xpath, aborting
                return None

            # if no remaining xpath, we are done
            if lxpath == [] or lxpath == ["text()"]:
                sql_field = field_name
                # final table
                sql_tables.append(ogr_layer_name)

                break

            # with a remaining xpath, it means there are other tables involved
            is_1_n = field_category in ('PATH_TO_CHILD_ELEMENT_NO_LINK', 'PATH_TO_CHILD_ELEMENT_WITH_LINK') and field_max_occurs > 1
            sql = """
select child_layer, child_pkid, parent_pkid
from {}_ogr_layer_relationships
where parent_layer='{}' and parent_element_name='{}'""".format(self._schema, ogr_layer_name, field_name)
            for f in self._ds.ExecuteSQL(sql):
                sql_joins.append((f.GetField("child_layer"),
                                  f.GetField("child_pkid"),
                                  ogr_layer_name,
                                  f.GetField("parent_pkid") if is_1_n else field_name))
                ogr_layer_name = f.GetField("child_layer")
                ogr_layer_pkid_name = f.GetField("child_pkid")
                break

        #print("sql_field", sql_field)
        #print("sql_tables", sql_tables)
        #print("sql_joins", sql_joins)

        # craft the SQL query to resolve XPath
        tables = set(sql_tables).union(set([t for (t, _, _, _) in sql_joins])).union(set([t for (_, _, t, _) in sql_joins]))
        for parent_table, parent_field, child_table, child_field in sql_joins:
            sql_wheres.append(((parent_table, parent_field), (child_table, child_field)))

        where = " and ".join(["{}.{} = {}.{}".format(l[0],l[1],r[0],r[1]) if isinstance(r, tuple) else "{}.{} = {}".format(l[0],l[1],r) for l, r in sql_wheres])
        sql = "select {} from {} where {}".format(sql_field, ", ".join(list(tables)), where)

        # execute SQL
        return [f.GetField(sql_field) for f in self._ds.ExecuteSQL(sql)]
    
