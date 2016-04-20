from __future__ import print_function
from xml_utils import split_tag, no_prefix
from pyxb.xmlschema.structures import Schema, ElementDeclaration, ComplexTypeDefinition, Particle, ModelGroup, SimpleTypeDefinition, Wildcard, AttributeUse, AttributeDeclaration
from schema_parser import parse_schemas
from type_resolver import resolve_types
from relational_model import *

import urllib2
import os
# for GML geometry to WKT
from osgeo import ogr

import xml.etree.ElementTree as ET

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
    if type not in ['Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon']:
        type = 'GeometryCollection'
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
        if r is not None:
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

    n_tag = no_prefix(node.tag)
    p = prefix + "/" if prefix != "" else ""

    for an, av in node.attrib.iteritems():
        n_an = no_prefix(an)
        if n_an == "id":
            # shared table, cannot be merged
            return None
        if n_an == "nil":
            continue
        cname = p + n_tag + "/@" + n_an
        au = ti.attribute_type_info_map()[an]
        columns.append(Column(cname,
                              ref_type = simple_type_to_sql_type(au.attributeDeclaration().typeDefinition()),
                              optional = True))
        #optional = not au.required()))

    if node.text is not None and len(node.text.strip()) > 0:
        cname = p + n_tag
        columns.append(Column(cname, ref_type = simple_type_to_sql_type(ti.type_info().typeDefinition()), optional = True))

    for child in node:
        child_columns = _merged_columns(child, p + n_tag, type_info_dict)
        if child_columns is not None:
            columns += child_columns

    return columns

def _build_tables(node, table_name, type_info_dict, tables):
    if len(node.attrib) == 0 and len(node) == 0:
        # empty table
        return None

    table = tables.get(table_name)
    if table is None:
        table = Table(table_name)
        tables[table_name] = table

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
        if not table.has_field("@" + n_attr_name):
            c = Column("@" + n_attr_name,
                       ref_type = simple_type_to_sql_type(au.attributeDeclaration().typeDefinition()),
                       optional = not au.required())
            table.add_field(c)
            if n_attr_name == "id":
                uid_column = c

    # id column
    if table.uid_column() is None:
        if uid_column is None:
            table.set_autoincrement_id()
        else:
            table.set_uid_column(uid_column)

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
            else:
                # simple type, 1:N cardinality => table
                child_table_name = no_prefix(node.tag) + "_" + no_prefix(child.tag)
                if not table.has_field(n_child_tag):
                    child_table = Table(child_table_name, [Column("text()", ref_type = simple_type_to_sql_type(child_td))])
                    tables[child_table_name] = child_table
                    table.add_field(Link(n_child_tag,
                                         is_optional,
                                         child_ti.min_occurs(),
                                         child_ti.max_occurs(),
                                         simple_type_to_sql_type(child_td), child_table))

        elif is_derived_from(child_td, "AbstractGeometryType"):
            # add geometry
            if not table.has_field(n_child_tag):
                gtype, gdim, gsrid = gml_geometry_type(child)
                table.add_field(Geometry(n_child_tag, gtype, gdim, gsrid))

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
                if r is not None and r[0] > 0:
                    child_columns = _merged_columns(child, "", type_info_dict)
                    for c in child_columns:
                        if not table.has_field(c.name()):
                            table.add_field(c)
                else:
                    _build_tables(child, child_table_name, type_info_dict, tables)
            else:
                # 1:N cardinality
                _build_tables(child, child_table_name, type_info_dict, tables)

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



def xpath_to_column_name(xpath):
    if xpath == "text()":
        return "v"
    return xpath.replace('/', '_').replace('@', '')

def resolve_xpath(node, xpath, trace = False):
    if trace:
        print("resolve_xpath", xpath)
    if xpath == "":
        return node.text

    path = xpath.split('/')
    leaf = path[0]

    if leaf == "text()":
        return node.text

    if no_prefix(node.tag) == leaf:
        return node
    
    if leaf.startswith("@"):
        for an, av in node.attrib.iteritems():
            if no_prefix(an) == leaf[1:]:
                return av
    
    nodes = []
    for child in node:
        if no_prefix(child.tag) == leaf:
            if len(path) == 1:
                nodes.append(child)
            else:
                return resolve_xpath(child, '/'.join(path[1:]), trace)

    if len(nodes) >= 1:
        return nodes

    # not found
    return None

def _populate(node, table, parent_id, tables_rows):
    if not isinstance(node, ET.Element):
        raise RuntimeError("Invalid type for node")
    table_name = table.name()
    rows = tables_rows.get(table_name)
    if rows is None:
        rows = []
        tables_rows[table_name] = rows
    row = []
    rows.append(row)

    # attributes
    current_id = None
    attr_cols = [c for c in table.columns() if c.name().startswith('@')]
    for attr_name, attr_value in node.attrib.iteritems():
        ns, n_attr_name = split_tag(attr_name)
        if '@' + n_attr_name in [c.name() for c in attr_cols]:
            row.append(('@' + n_attr_name, attr_value))
            if n_attr_name == "id":
                current_id = attr_value
    if current_id is None:
        if table.has_autoincrement_id():
            current_id = table.increment_id()
            row.append(("id", current_id))

   # columns
    cols = [c for c in table.columns() if not c.name().startswith('@')]
    for c in cols:
        child = resolve_xpath(node, c.name())
        if child is None:
            continue
        if isinstance(child, (str, unicode)):
            v = child
        else:
            v = child[0].text
        if v is None:
            v = ''
        row.append((xpath_to_column_name(c.name()), v))

    # links
    for link in table.links():
        if link.max_occurs() is not None:
            child = resolve_xpath(node, link.name())
            if child is None:
                continue
            child_id = _populate(child[0], link.ref_table(), current_id, tables_rows)
            row.append((link.name() + "_id", child_id))
        else:
            children = resolve_xpath(node, link.name())
            if children is None:
                continue
            for child in children:
                _populate(child, link.ref_table(), current_id, tables_rows)

    # backlinks
    for bl in table.back_links():
        row.append((bl.ref_table().name() + "_id", parent_id))

    # geometry
    geometries = table.geometries()
    if len(geometries) > 0:
        geom = geometries[0]
        g_nodes = resolve_xpath(node, geom.name())
        if g_nodes is not None:
            g = ogr.CreateGeometryFromGML(ET.tostring(g_nodes[0]))
            row.append((geom.name(), ("GeomFromText('%s', %d)", g.ExportToWkt(), geom.srid())))

    return current_id
    
def build_tables(root_node, type_info_dict, tables = None):
    """Creates or updates table definitions from a document and its TypeInfo dict
    :param root_node: the root node
    :param type_info_dict: the TypeInfo dict
    :param tables: the existing table dict to update
    :returns: {table_name : Table}
    """
    if tables is None:
        tables = {}
        
    table_name = no_prefix(root_node.tag)
    _build_tables(root_node, table_name, type_info_dict, tables)

    # create backlinks
    for name, table in tables.iteritems():
        for link in table.links():
            # only for links with a "*" cardinality
            if link.max_occurs() is None and link.ref_table() is not None:
                if not link.ref_table().has_field(link.name()):
                    link.ref_table().add_back_link(link.name(), table)

    return tables

class URIResolver(object):
    def __init__(self, cachedir, urlopener = urllib2.urlopen):
        self.__cachedir = cachedir
        self.__urlopener = urlopener

    def cache_uri(self, uri, parent_uri = '', lvl = 0):
        def mkdir_p(path):
            """Recursively create all subdirectories of a given path"""
            dirs = path.split('/')
            if dirs[0] == '':
                p = '/'
                dirs = dirs[1:]
            else:
                p = ''
            for d in dirs:
                p = os.path.join(p, d)
                if not os.path.exists(p):
                    os.mkdir(p)

        print(" "*lvl, "Resolving schema {} ... ".format(uri))

        if not uri.startswith('http://'):
            if uri.startswith('/'):
                # absolute file name
                return uri
            uri = parent_uri + uri
        base_uri = 'http://' + '/'.join(uri[7:].split('/')[:-1]) + "/"

        out_file_name = uri
        if uri.startswith('http://'):
            out_file_name = uri[7:]
        out_file_name = os.path.join(self.__cachedir, out_file_name)
        if os.path.exists(out_file_name):
            return out_file_name
        
        f = self.__urlopener(uri)
        mkdir_p(os.path.dirname(out_file_name))
        fo = open(out_file_name, "w")
        fo.write(f.read())
        fo.close()
        f.close()

        # process imports
        doc = ET.parse(out_file_name)
        root = doc.getroot()

        for child in root:
            n_child_tag = no_prefix(child.tag)
            if n_child_tag == "import" or n_child_tag == "include":
                for an, av in child.attrib.iteritems():
                    if no_prefix(an) == "schemaLocation":
                        self.cache_uri(av, base_uri, lvl+2)
        return out_file_name
    
    def data_from_uri(self, uri):
        out_file_name = self.cache_uri(uri)
        f = open(out_file_name)
        return f.read()

def extract_features(doc):
    """Extract (Complex) features from a XML doc
    :param doc: a DOM document
    :returns: a list of nodes for each feature
    """
    nodes = []
    root = doc.getroot()
    if root.tag.startswith(u'{http://www.opengis.net/wfs') and root.tag.endswith('FeatureCollection'):
        # WFS features
        for child in root:
            if no_prefix(child.tag) == 'member':
                nodes.append(child[0])
            elif no_prefix(child.tag) == 'featureMembers':
                for cchild in child:
                    nodes.append(cchild)
    else:
        # it seems to be an isolated feature
        nodes.append(root)
    return nodes


def load_gml_model(xml_file, archive_dir, xsd_files = []):
    cachefile = os.path.join(archive_dir, xml_file + ".model")

    if os.path.exists(cachefile):
        print("Model loaded from " + cachefile)
        return load_model_from(cachefile)

    uri_resolver = URIResolver(archive_dir)

    doc = ET.parse(xml_file)
    features = extract_features(doc)
    root = features[0]
    root_ns, root_name = split_tag(root.tag)

    if len(xsd_files) == 0:
        # try to download schemas
        root = doc.getroot()
        for an, av in root.attrib.iteritems():
            if no_prefix(an) == "schemaLocation":
                xsd_files = [uri_resolver.cache_uri(x) for x in av.split()[1::2]]

    if len(xsd_files) == 0:
        raise RuntimeError("No schema found")

    ns_map = parse_schemas(xsd_files, urlopen = lambda uri : uri_resolver.data_from_uri(uri))
    ns = ns_map[root_ns]
    root_type = ns.elementDeclarations()[root_name].typeDefinition()

    tables = None
    tables_rows = {}
    for idx, node in enumerate(features):
        print("+ Feature #{}/{}".format(idx+1, len(features)))
        type_info_dict = resolve_types(node, ns_map)
        tables = build_tables(node, type_info_dict, tables)
    for idx, node in enumerate(features):
        print("+ Feature #{}/{}".format(idx+1, len(features)))
        type_info_dict = resolve_types(node, ns_map)
        _populate(node, tables[root_name], None, tables_rows)
        

    model = Model(tables, tables_rows, root_name)
    save_model_to(model, cachefile)
    
    return model
