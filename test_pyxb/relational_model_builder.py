from xml_utils import split_tag, no_prefix
from pyxb.xmlschema.structures import Schema, ElementDeclaration, ComplexTypeDefinition, Particle, ModelGroup, SimpleTypeDefinition, Wildcard, AttributeUse, AttributeDeclaration
from relational_model import *

def is_simple(td):
    return isinstance(td, SimpleTypeDefinition) or (isinstance(td, ComplexTypeDefinition) and td.contentType()[0] == 'SIMPLE')
        
def is_derived_from(td, type_name):
    while td.name() != "anyType":
        if td.name() == type_name:
            return True
        td = td.baseTypeDefinition()
    return False

def simple_type_to_sql_type(td):
    if td.name() == "anyType":
        return "TEXT"
    std = None
    if isinstance(td, ComplexTypeDefinition):
        if td.contentType()[0] == 'SIMPLE':
            # complex type with simple content
            std = td.contentType()[1]
    elif isinstance(td, SimpleTypeDefinition):
        std = td
    type_name = ""
    if std:
        if std.variety() == SimpleTypeDefinition.VARIETY_list:
            std = std.itemTypeDefinition()
            type_name += "list of "
        if std.variety() == SimpleTypeDefinition.VARIETY_atomic and std.primitiveTypeDefinition() != std:
            type_name += std.primitiveTypeDefinition().name()
        else:
            type_name += std.name()
    else:
        raise RuntimeError("Not simple type" + repr(td))
    type_map = {u'string': u'TEXT',
                u'integer' : u'INT',
                u'decimal' : u'INT',
                u'boolean' : u'BOOLEAN',
                u'NilReasonType' : u'TEXT',
                u'anyURI' : u'TEXT'
    }
    return type_map.get(type_name) or type_name

def gml_geometry_type(node):
    import re
    srid = None
    dim = 2
    type = no_prefix(node.tag)
    if type in ['Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon']:
        type = type.upper()
    else:
        type = 'GEOMETRYCOLLECTION'
    for k, v in node.attrib.iteritems():
        if no_prefix(k) == 'srsDimension':
            dim = int(v)
        elif no_prefix(k) == 'srsName':
            # EPSG:4326
		  	# urn:EPSG:geographicCRS:4326
		  	# urn:ogc:def:crs:EPSG:4326
		 	# urn:ogc:def:crs:EPSG::4326
		  	# urn:ogc:def:crs:EPSG:6.6:4326
		   	# urn:x-ogc:def:crs:EPSG:6.6:4326
			# http://www.opengis.net/gml/srs/epsg.xml#4326
			# http://www.epsg.org/6.11.2/4326
            # get the last number
            m = re.search('([0-9]+)/?$', v)
            srid = int(m.group(1))
    return type, dim, srid

def _simple_cardinality_size(node, type_info_dict):
    """Compute the number of new columns that would be created if every children with simple cardinality are merged
    :returns: (width, depth) width is the number of news columns that would be created
    and depth is the maximum depth of these columns (number of child levels)
    """
    ti = type_info_dict[node]
    if ti.max_occurs() is None:
        # not simple cardinality
        return None
    if is_derived_from(ti.type_info().typeDefinition(), "AbstractGeometryType"):
        # geometry, cannot merge
        return None

    if "id" in [no_prefix(an) for an in node.attrib.keys()]:
        # shared table, cannot be merged
        return None
            
    width = len(node.attrib)
    depth = 1

    if node.text is not None and len(node.text.strip()) > 0:
        width += 1

    for child in node:
        r = _simple_cardinality_size(child, type_info_dict)
        if r is None:
            return None
        child_width, child_depth = r
        width += child_width
        if child_depth + 1 > depth:
            depth = child_depth + 1

    return (width, depth)

def _merged_columns(node, prefix, type_info_dict):
    ti = type_info_dict[node]
    if ti.max_occurs() is None:
        # not simple cardinality
        return None
    if is_derived_from(ti.type_info().typeDefinition(), "AbstractGeometryType"):
        # geometry, cannot merge
        return None

    columns = []
    values = []

    n_tag = no_prefix(node.tag)
    p = prefix + "_" if prefix != "" else ""

    for an, av in node.attrib.iteritems():
        n_an = no_prefix(an)
        if n_an == "id":
            # shared table, cannot be merged
            return None
        if n_an == "nil":
            continue
        cname = p + n_tag + "_" + n_an
        au = ti.attribute_type_info_map()[an]
        columns.append(Column(cname,
                              ref_type = simple_type_to_sql_type(au.attributeDeclaration().typeDefinition()),
                              optional = True))
        #optional = not au.required()))
        values.append((cname, av))

    if node.text is not None and len(node.text.strip()) > 0:
        cname = p + n_tag
        columns.append(Column(cname, ref_type = simple_type_to_sql_type(ti.type_info().typeDefinition()), optional = True))
        values.append((cname, node.text))

    for child in node:
        r = _merged_columns(child, p + n_tag, type_info_dict)
        if r is None:
            return None
        child_columns, child_values = r
        columns += child_columns
        values += child_values

    return columns, values

def _build_tables(node, table_name, parent_id, type_info_dict, tables, tables_rows):
    if len(node.attrib) == 0 and len(node) == 0:
        # empty table
        return None
    print("Build table", table_name)

    table = tables.get(table_name)
    if table is None:
        table = Table(table_name)
        tables[table_name] = table
        tables_rows[table_name] = []
    table_rows = tables_rows[table_name]

    row = []
    table_rows.append(row)

    if parent_id is not None:
        row.append(parent_id)

    uid_column = None
    ti = type_info_dict[node]
    current_id = None
    #--------------------------------------------------
    # attributes
    #--------------------------------------------------
    for attr_name, attr_value in node.attrib.iteritems():
        ns, n_attr_name = split_tag(attr_name)
        if ns == "http://www.w3.org/2001/XMLSchema-instance":
            continue

        au = ti.attribute_type_info_map()[attr_name]
        if not table.has_field(n_attr_name):
            c = Column(n_attr_name,
                       ref_type = simple_type_to_sql_type(au.attributeDeclaration().typeDefinition()),
                       optional = not au.required())
            table.add_field(c)
            if n_attr_name == "id":
                uid_column = c

        row.append((n_attr_name, attr_value))
        if n_attr_name == "id":
            current_id = attr_value

    # id column
    if table.uid_column() is None:
        if uid_column is None:
            table.set_autoincrement_id()
        else:
            table.set_uid_column(uid_column)

    if table.has_autoincrement_id():
        current_id = table.increment_id()
        row.append(("id", current_id))

    #--------------------------------------------------
    # child elements
    #--------------------------------------------------
    # in a sequence ?
    in_seq = False
    # tag of the sequence
    seq_tag = None
    for child in node:
        child_ti = type_info_dict[child]
        child_td = child_ti.type_info().typeDefinition()
        n_child_tag = no_prefix(child.tag)
        
        if child_ti.max_occurs() is None: # "*" cardinality
            if not (in_seq and seq_tag == child.tag):
                in_seq = True
                seq_tag = child.tag
        else:
            in_seq = False

        is_optional = child_ti.min_occurs() == 0 or child_ti.type_info().nillable()
        if is_simple(child_td):
            if not in_seq:
                # simple type, 1:1 cardinality => column
                if not table.has_field(n_child_tag):
                    table.add_field(Column(n_child_tag,
                                           ref_type = simple_type_to_sql_type(child_td),
                                           optional = is_optional))

                v = child.text if child.text is not None else '' # FIXME replace by the default value ?
                row.append((no_prefix(child.tag), v))
            else:
                # simple type, 1:N cardinality => table
                child_table_name = no_prefix(node.tag) + "_" + no_prefix(child.tag)
                if not table.has_field(n_child_tag):
                    child_table = Table(child_table_name, [Column("v", ref_type = simple_type_to_sql_type(child_td))])
                    tables[child_table_name] = child_table
                    tables_rows[child_table_name] = []
                    table.add_field(Link(n_child_tag,
                                         is_optional,
                                         child_ti.min_occurs(),
                                         child_ti.max_occurs(),
                                         simple_type_to_sql_type(child_td), child_table))
                    print("#", table.name(), "is linked to", child_table_name, "via", n_child_tag)

                v = child.text if child.text is not None else ''
                child_table_rows = tables_rows[child_table_name]
                child_row = [(table_name + "_id", current_id), ("v", v)]
                child_table_rows.append(child_row)                

        elif is_derived_from(child_td, "AbstractGeometryType"):
            # add geometry
            if not table.has_field(n_child_tag):
                gtype, gdim, gsrid = gml_geometry_type(child)
                table.add_field(Geometry(n_child_tag, gtype, gdim, gsrid))
            
            g_column = table.field(n_child_tag)
            g = ogr.CreateGeometryFromGML(ET.tostring(child))
            row.append((n_child_tag, ("GeomFromText('%s', %d)", g.ExportToWkt(), g_column.srid())))

        else:
            has_id = any([1 for n in child.attrib.keys() if no_prefix(n) == "id"])
            if has_id:
                # shared table
                child_table_name = child_td.name() or no_prefix(node.tag) + "_t"
            else:
                child_table_name = table_name + "_"  + no_prefix(child.tag)
            if not in_seq:
                # 1:1 cardinality
                r = _simple_cardinality_size(child, type_info_dict)
                if r is not None:
                    child_columns, child_values = _merged_columns(child, "", type_info_dict)
                    for c in child_columns:
                        if not table.has_field(c.name()):
                            table.add_field(c)
                    row += child_values
                else:
                    row_id = _build_tables(child, child_table_name, None, type_info_dict, tables, tables_rows)
                    row.append((n_child_tag + "_id", row_id))
            else:
                # 1:N cardinality
                child_parent_id = (table_name + "_id", current_id)
                _build_tables(child, child_table_name, child_parent_id, type_info_dict, tables, tables_rows)

            child_table = tables.get(child_table_name)
            if child_table is not None: # may be None if the child_table is empty
                # create link
                if not table.has_field(n_child_tag):
                    sgroup = None
                    if child_ti.abstract_type_info() is not None:
                        sgroup = child_ti.abstract_type_info().name()
                    table.add_field(Link(n_child_tag,
                                         is_optional,
                                         child_ti.min_occurs(),
                                         child_ti.max_occurs(),
                                         None,
                                         child_table,
                                         substitution_group = sgroup))

    # return last inserted id
    return current_id


def build_tables(root_node, type_info_dict, tables = None, tables_rows = None):
    """Creates or updates table definitions from a document and its TypeInfo dict
    :param root_node: the root node
    :param type_info_dict: the TypeInfo dict
    :param tables: the existing table dict to update
    :param tables_rows: the existing tables rows to update
    :returns: ({table_name : Table}, {table_name : rows})
    """
    if tables is None:
        tables = {}
    if tables_rows is None:
        tables_rows = {}
        
    table_name = no_prefix(root_node.tag)
    _build_tables(root_node, table_name, None, type_info_dict, tables, tables_rows)

    # create backlinks
    for name, table in tables.iteritems():
        for link in table.links():
            # only for links with a "*" cardinality
            if link.max_occurs() is None and link.ref_table() is not None:
                if not link.ref_table().has_field(link.name()):
                    print(link.ref_table().name(), "backlink to", table.name())
                    link.ref_table().add_back_link(link.name(), table)
    return tables, tables_rows

