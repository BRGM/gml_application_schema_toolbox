from __future__ import print_function
import logging
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

def gml_geometry_type(node, td):
    import re
    srid = None
    dim = 2
    type = no_prefix(node.tag)
    if type not in ['Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon']:
        tmap = {'PointType' : 'Point',
                'LineStringType' : 'LineString',
                'PolygonType' : 'Polygon',
                'MultiPointType': 'MultiPoint',
                'MultiLineStringType': 'MultiLineString',
                'MultiPolygonType': 'MultiPolygon'}
        if tmap.get(td.name()) is not None:
            type = tmap[td.name()]
        else:
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
    if is_derived_from(ti.type_info().typeDefinition(), "AbstractGeometryType"):
        # geometry, cannot merge
        return None

    columns = []

    n_tag = no_prefix(node.tag)
    p = prefix + "/" if prefix != "" else ""

    for an, av in node.attrib.iteritems():
        ns, n_an = split_tag(an)
        if n_an == "id":
            # shared table, cannot be merged
            return None
        if ns == "http://www.w3.org/2001/XMLSchema-instance":
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

def _build_tables2(node, table_name, type_info_dict, tables, merge_max_depth):
    """
    :param node: the DOM node
    :param table_name: the table name corresponding to this node
    :param type_info_dict: dict that gives type information on a node
    :param tables: the input/output dict {table_name: Table}
    :param merge_max_depth: the maximum depth to consider when tables are merged
    """
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
        if not table.has_field(n_attr_name):
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
    last_tag = None
    for child in node:
        child_ti = type_info_dict[child]
        child_td = child_ti.type_info().typeDefinition()
        n_child_tag = no_prefix(child.tag)

        in_seq = n_child_tag == last_tag
        last_tag = n_child_tag

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
                for f in table.columns():
                    if f.xpath().startswith(n_child_tag):
                        # this column is now part of a sequence, remove the column
                        # a link will be created
                        table.remove_field(f.name())

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
                if r is not None and r[0] > 0 and r[1] < merge_max_depth:
                    child_columns = _merged_columns(child, "", type_info_dict)
                    for c in child_columns:
                        if not table.has_field(c.name()):
                            table.add_field(c)
                else:
                    _build_tables(child, child_table_name, type_info_dict, tables, merge_max_depth)
            else:
                for f in table.columns():
                    if f.xpath().startswith(n_child_tag):
                        # this (potentially merged) column is now part of a sequence, remove the column
                        # a link will be created
                        table.remove_field(f.name())
                # 1:N cardinality
                _build_tables(child, child_table_name, type_info_dict, tables, merge_max_depth)

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

def merge_tables(table1, table2):
    table1_fields = set(table1.fields().values())
    table2_fields = set(table2.fields().values())
    merged_fields = table1_fields | table2_fields # union
    merged = table1.clone()
    merged.set_fields(merged_fields)
    return merged
    
    
def _build_table(node, table_name, type_info_dict, merge_max_depth, merge_sequences = False, share_geometries = False):
    """
    :param merge_max_depth: Maximum acceptable merging depth
    :param merge_sequences: Whether to merge unitary sequences or not
    :param share_geometries: Whether to regroup geometries of the same type in a common layer
    :returns: a dict {table_name: Table}
    """
    
    table = Table(table_name)

    if len(node.attrib) == 0 and len(node) == 0 and (node.text is None or len(node.text) == 0):
        # empty table
        return table

    ti = type_info_dict[node]
    node_td = ti.type_info().typeDefinition()

    if is_derived_from(node_td, "AbstractGeometryType"):
        #
        # special case for the geometry
        #
        is_optional = ti.min_occurs() == 0 or ti.type_info().nillable()
        gtype, gdim, gsrid = gml_geometry_type(node, node_td)
        table.add_field(Geometry("geometry()", gtype, gdim, gsrid, optional = is_optional))
        # look for an id
        for attr_name, attr_value in node.attrib.iteritems():
            ns, n_attr_name = split_tag(attr_name)
            if n_attr_name == "id":
                au = ti.attribute_type_info_map()[attr_name]
                c = Column("@id",
                           ref_type = simple_type_to_sql_type(au.attributeDeclaration().typeDefinition()),
                           optional = not au.required())
                table.add_field(c)
                if share_geometries:
                    table.set_uid_column(c)
        if table.uid_column() is None:
            table.set_autoincrement_id()
                
        return table
    
    uid_column = None
    current_id = None
    #--------------------------------------------------
    # attributes
    #--------------------------------------------------
    for attr_name, attr_value in node.attrib.iteritems():
        ns, n_attr_name = split_tag(attr_name)
        if ns == "http://www.w3.org/2001/XMLSchema-instance":
            continue

        au = ti.attribute_type_info_map()[attr_name]
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

    if is_simple(node_td):
        if node.text is not None and len(node.text.strip()) > 0:
            is_optional = ti.min_occurs() == 0 or ti.type_info().nillable()
            table.add_field(Column("text()",
                                   ref_type = simple_type_to_sql_type(ti.type_info().typeDefinition()),
                                   optional = is_optional))

    #--------------------------------------------------
    # child elements
    #--------------------------------------------------
    # are we in a sequence with more than one element ?
    in_seq = False
    # tag of the sequence
    last_tag = None
    child_table = None
    last_child_table = None
    for child in node:
        child_ti = type_info_dict[child]
        child_td = child_ti.type_info().typeDefinition()
        n_child_tag = no_prefix(child.tag)

        in_seq = n_child_tag == last_tag
        last_tag = n_child_tag
        is_seq = child_ti.max_occurs() is None

        simple_child_type = None
        if is_simple(child_td):
            simple_child_type = simple_type_to_sql_type(child_td)

        is_optional = child_ti.min_occurs() == 0 or child_ti.type_info().nillable()

        has_id = any([1 for n in child.attrib.keys() if no_prefix(n) == "id"])
        if has_id:
            # shared table
            child_table_name = child_td.name() or table_name + "_" + n_child_tag + "_t"
        else:
            child_table_name = table_name + "_"  + n_child_tag

        if in_seq or (is_seq and not merge_sequences):
            if in_seq and child_table is not None:
                last_child_table = child_table
            child_table = _build_table(child, child_table_name, type_info_dict, merge_max_depth, merge_sequences, share_geometries)
            if in_seq and last_child_table is not None:
                child_table = merge_tables(last_child_table, child_table)
            table.add_field(Link(n_child_tag,
                                 is_optional,
                                 child_ti.min_occurs(),
                                 child_ti.max_occurs(),
                                 ref_type = simple_child_type,
                                 ref_table = child_table))
            for c in table.columns() + table.geometries():
                if c.xpath().startswith(n_child_tag+"[0]"):
                    # it was a merged column, now a link is created, remove it
                    table.remove_field(c.name())
        else:
            child_table = _build_table(child, child_table_name, type_info_dict, merge_max_depth, merge_sequences, share_geometries)
            if child_table.is_mergeable() and child_table.max_field_depth() + 1 < merge_max_depth:
                suffix = "/"
                if is_seq: # defined as a sequence, but potentially merged
                    suffix = "[0]/"
                for field in child_table.fields().values():
                    if field.name() == "id":
                        continue
                    f = field.clone()
                    f.set_xpath(n_child_tag + suffix + field.xpath())
                    table.add_field(f)
            else:
                # FIXME substitution group
                table.add_field(Link(n_child_tag,
                                     is_optional,
                                     child_ti.min_occurs(),
                                     child_ti.max_occurs(),
                                     ref_type = simple_child_type,
                                     ref_table = child_table))

    return table

def resolve_xpath(node, xpath):
    path = xpath.split('/')
    part = path[0]

    if part == '':
        return node

    if part == "text()":
        if node.text is None:
            return ""
        return node.text

    if part == "geometry()":
        return node

    if part.startswith("@"):
        for an, av in node.attrib.iteritems():
            if no_prefix(an) == part[1:]:
                return av
    
    found = []
    for child in node:
        n_child_tag = no_prefix(child.tag)
        if n_child_tag == part:
            found.append(child)
        elif part.endswith("[0]") and n_child_tag == part[0:-3]:
            found.append(child)
            # only retain the first child
            break
    nodes = []
    for child in found:
        p = resolve_xpath(child, '/'.join(path[1:]))
        if p is not None:
            if isinstance(p, list):
                nodes.extend(p)
            else:
                nodes.append(p)

    if len(nodes) == 0:
        return None
    elif len(nodes) == 1:
        return nodes[0]
    else:
        return nodes

def _populate(node, table, parent_id, tables_rows):
    if len(node.attrib) == 0 and len(node) == 0:
        # empty table
        return None
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
    attr_cols = [c for c in table.columns() if c.xpath().startswith('@')]
    for attr_name, attr_value in node.attrib.iteritems():
        ns, n_attr_name = split_tag(attr_name)
        if n_attr_name in [c.name() for c in attr_cols]:
            row.append((n_attr_name, attr_value))
            if n_attr_name == "id":
                current_id = attr_value
    if current_id is None:
        if table.has_autoincrement_id():
            current_id = table.increment_id()
            row.append(("id", current_id))
        else:
            raise RuntimeError("No id for node {} in table {} {}".format(node.tag, table.name(), table))

    # columns
    cols = [c for c in table.columns() if not c.xpath().startswith('@')]
    for c in cols:
        child = resolve_xpath(node, c.xpath())
        if child is None:
            if not c.optional():
                raise ValueError("Required value {} for element {} not found".format(c.xpath(), node.tag))
            continue
        if isinstance(child[0], (str, unicode)):
            v = child[0]
        else:
            v = child[0].text
        row.append((c.name(), v))

    # links
    for link in table.links():
        if link.max_occurs() is not None:
            child = resolve_xpath(node, link.xpath())
            if child is None:
                if not link.optional():
                    raise ValueError("Required child {} for element {} not found".format(link.xpath(), node.tag))
                continue
            child_id = _populate(child, link.ref_table(), current_id, tables_rows)
            row.append((link.name() + "_id", child_id))
        else:
            children = resolve_xpath(node, link.xpath())
            if children is None:
                if not link.optional():
                    raise ValueError("Required children {} for element {} not found".format(link.xpath(), node.tag))
                continue
            for child in children:
                _populate(child, link.ref_table(), current_id, tables_rows)

    # backlinks
    for bl in table.back_links():
        row.append((bl.ref_table().name() + "_id", parent_id))

    # geometry
    for geom in table.geometries():
        g_nodes = resolve_xpath(node, geom.xpath())
        if g_nodes is not None:
            g = ogr.CreateGeometryFromGML(ET.tostring(g_nodes))
            if g is not None:
                row.append((geom.name(), ("GeomFromText('%s', %d)", g.ExportToWkt(), geom.srid())))

    return current_id
    
def build_tables(root_node, type_info_dict, tables, merge_max_depth, merge_sequences, share_geometries):
    """Creates or updates table definitions from a document and its TypeInfo dict
    :param root_node: the root node
    :param type_info_dict: the TypeInfo dict
    :param tables: the existing table dict to update
    :param merge_max_depth: the maximum depth to consider when merging tables
    :returns: {table_name : Table}
    """
        
    if tables is None:
        tables = {}
    table_name = no_prefix(root_node.tag)
    if False:
        _build_tables(root_node, table_name, type_info_dict, tables, merge_max_depth)
    else:
        table = _build_table(root_node, table_name, type_info_dict, merge_max_depth, merge_sequences, share_geometries)
        def collect_tables(table, tables):
            t = [table]
            tables[table.name()] = table
            for link in table.links():
                etable = tables.get(link.ref_table().name())
                if etable is not None:
                    ntable = merge_tables(etable, link.ref_table())
                    link.set_ref_table(ntable)
                t.extend(collect_tables(link.ref_table(), tables))
            return t
        collect_tables(table, tables)

    # create backlinks
    for name, table in tables.iteritems():
        for link in table.links():
            # only for links with a "*" cardinality
            if link.max_occurs() is None and link.ref_table() is not None:
                if not link.ref_table().has_field(link.name()):
                    link.ref_table().add_back_link(link.name(), table)

    return tables

def uri_is_absolute(uri):
    return uri.startswith('http://') or os.path.isabs(uri)

def uri_dirname(uri):
    if uri.startswith('http://'):
        return "http://" + os.path.dirname(uri[7:])
    return os.path.dirname(uri)

def uri_join(uri, path):
    return os.path.join(uri, path)

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

        logging.info(" "*lvl + "Resolving schema {} ... ".format(uri))

        if not uri.startswith('http://'):
            if uri.startswith('/'):
                # absolute file name
                return uri
            else:
                # relative file name
                uri = os.path.join(parent_uri, uri)
                return uri

        base_uri = uri_dirname(uri)

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


def load_gml_model(xml_file, archive_dir, xsd_files = [], merge_max_depth = 6, merge_sequences = False, share_geometries = False, split_multi_geometries = True, urlopener = urllib2.urlopen, use_cache_file = False):
    cachefile = os.path.join(archive_dir, os.path.basename(xml_file) + ".model")

    if use_cache_file and os.path.exists(cachefile):
        logging.info("Model loaded from " + cachefile)
        return load_model_from(cachefile)

    doc = ET.parse(xml_file)
    features = extract_features(doc)
    root = features[0]
    root_ns, root_name = split_tag(root.tag)

    uri_resolver = URIResolver(archive_dir, urlopener)

    parent_uri = os.path.dirname(xml_file)

    if len(xsd_files) == 0:
        # try to download schemas
        root = doc.getroot()
        for an, av in root.attrib.iteritems():
            if no_prefix(an) == "schemaLocation":
                xsd_files = [uri_resolver.cache_uri(x, parent_uri) for x in av.split()[1::2]]

    if len(xsd_files) == 0:
        raise RuntimeError("No schema found")

    ns_map = parse_schemas(xsd_files, urlopen = lambda uri : uri_resolver.data_from_uri(uri))

    ns = ns_map[root_ns]
    root_type = ns.elementDeclarations()[root_name].typeDefinition()

    tables = None
    tables_rows = {}
    logging.info("Tables construction ...")
    for idx, node in enumerate(features):
        logging.info("+ Feature #{}/{}".format(idx+1, len(features)))
        type_info_dict = resolve_types(node, ns_map)
        tables = build_tables(node, type_info_dict, tables, merge_max_depth, merge_sequences, share_geometries)

    # split multi geometry tables if asked to
    if split_multi_geometries:
        new_tables = []
        for table_name, table in tables.iteritems():
            if len(table.geometries()) > 1:
                for geometry in table.geometries():
                    xpath1 = '/'.join(geometry.xpath().split('/')[0:-1])
                    xpath2 = geometry.xpath().split('/')[-1]
                    new_geometry = Geometry(xpath2, geometry.type(), geometry.dimension(), geometry.srid(), optional = False)
                    new_table = Table(table_name + "_" + xpath_to_column_name(xpath1), [new_geometry])
                    new_table.set_autoincrement_id()
                    new_link = Link(xpath1, geometry.optional(), 1, 1, 'INT', ref_table = new_table)
                    table.remove_field(geometry.name())
                    table.add_field(new_link)
                    new_tables.append(new_table)
        for table in new_tables:
            tables[table.name()] = table
                    
    logging.info("Tables population ...")
    for idx, node in enumerate(features):
        logging.info("+ Feature #{}/{}".format(idx+1, len(features)))
        type_info_dict = resolve_types(node, ns_map)
        _populate(node, tables[root_name], None, tables_rows)
        

    model = Model(tables, tables_rows, root_name)
    if use_cache_file:
        save_model_to(model, cachefile)
    
    return model
