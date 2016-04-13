#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import logging
logging.basicConfig()

import sys
sys.path = ['/home/hme/src/pyxb'] + sys.path

from pyxb.xmlschema.structures import Schema, ElementDeclaration, ComplexTypeDefinition, Particle, ModelGroup, SimpleTypeDefinition, Wildcard, AttributeUse, AttributeDeclaration

from schema_parser import parse_schemas
from type_resolver import resolve_types, no_prefix, type_definition_name

import os
import sys
import urllib2

import xml.etree.ElementTree as ET
# for GML geometry to WKT
from osgeo import ogr

import pickle

class URIResolver(object):
    def __init__(self, cachedir):
        self.__cachedir = cachedir

    def cache_uri(self, uri):
        def mkdir_p(path):
            """Recursively create all subdirectories of a given path"""
            dirs = path.split('/')
            p = ""
            for d in dirs:
                p = os.path.join(p, d)
                if not os.path.exists(p):
                    os.mkdir(p)

        if uri.startswith('http://'):
            base_uri = 'http://' + '/'.join(uri[7:].split('/')[:-1])
        else:
            base_uri = os.path.dirname(uri)

        print("Resolving schema {} ... ".format(uri), end="")

        out_file_name = uri
        if uri.startswith('http://'):
            out_file_name = uri[7:]
        out_file_name = os.path.join(self.__cachedir, out_file_name)
        if not os.path.exists(out_file_name):
            f = urllib2.urlopen(uri)
            mkdir_p(os.path.dirname(out_file_name))
            fo = open(out_file_name, "w")
            fo.write(f.read())
            fo.close()
            f.close()
        print("OK")
        return out_file_name
    
    def data_from_uri(self, uri):
        out_file_name = self.cache_uri(uri)
        f = open(out_file_name)
        return f.read()

def print_schema(obj, lvl):
    print(" " * lvl, obj.__class__.__name__, end=" ")
    if isinstance(obj, ElementDeclaration):
        print("<" + obj.name() + ">")
#        if obj.typeDefinition():
#            print("typeDefinition ->")
#            print_schema(obj.typeDefinition(), lvl+2)
#        else:
#            print
    elif isinstance(obj, ComplexTypeDefinition):
        contentType = obj.contentType()
        if contentType:
            print("contentType", contentType, "->")
            if isinstance(contentType, tuple):
                print_schema(contentType[1], lvl+2)
            else:
                print_schema(contentType, lvl+2)
    elif isinstance(obj, SimpleTypeDefinition):
        print(obj.name())
    elif isinstance(obj, Particle):
        print(obj.minOccurs(), "-", obj.maxOccurs(), end=" ")
        if obj.term():
            print("term ->")
            print_schema(obj.term(), lvl+2)
        else:
            print()
    elif isinstance(obj, ModelGroup):
        print(obj.compositorToString(), len(obj.particles()), "particles")
        for p in obj.particles():
            print_schema(p, lvl+2)


class Link:
    """A Link represents a link to another type/table"""

    def __init__(self, name, optional, min_occurs, max_occurs, ref_type, ref_table = None, substitution_group = None):
        self.__name = name
        self.__optional = optional
        self.__min_occurs = min_occurs
        self.__max_occurs = max_occurs
        self.__ref_type = ref_type # SQL type (str)
        self.__ref_table = ref_table # Table
        self.__substitution_group = substitution_group # for element that derives from a common element

    def name(self):
        return self.__name
    def ref_type(self):
        return self.__ref_type
    def ref_table(self):
        return self.__ref_table
    def set_ref_table(self, ref_table):
        self.__ref_table = ref_table
    def optional(self):
        return self.__optional
    def min_occurs(self):
        return self.__min_occurs
    def max_occurs(self):
        return self.__max_occurs
    def substitution_group(self):
        return self.__substitution_group

    def __repr__(self):
        return "Link<{}({}-{}){}>".format(self.name(), self.min_occurs(),
                                          "*" if self.max_occurs() is None else self.max_occurs(),
                                          "" if self.ref_table() is None else " " + self.ref_table().name())

class BackLink:
    """A BackLink represents a foreign key relationship"""

    def __init__(self, name, ref_table):
        self.__name = name
        self.__ref_table = ref_table

    def name(self):
        return self.__name
    def ref_table(self):
        return self.__ref_table

    def __repr__(self):
        return "BackLink<{}({})>".format(self.name(), self.ref_table().name())

class Column:
    """A Column is a (simple type) column"""

    def __init__(self, name, optional = False, ref_type = None, auto_incremented = False):
        self.__name = name
        self.__optional = optional
        self.__ref_type = ref_type
        self.__auto_incremented = auto_incremented

    def name(self):
        return self.__name
    def ref_type(self):
        return self.__ref_type
    def optional(self):
        return self.__optional
    def auto_incremented(self):
        return self.__auto_incremented

    def __repr__(self):
        return "Column<{}{}>".format(self.__name, " optional" if self.__optional else "")

class Geometry:
    """A geometry column"""

    def __init__(self, name, type, dim, srid, optional = False):
        self.__name = name
        self.__type = type
        self.__dim = dim
        self.__srid = srid
        self.__optional = optional

    def name(self):
        return self.__name
    def type(self):
        return self.__type
    def dimension(self):
        return self.__dim
    def srid(self):
        return self.__srid
    def optional(self):
        return self.__optional
    def __repr__(self):
        return "Geometry<{} {}{}({}){}>".format(self.name(), self.type(), "Z" if self.dimension() == 3 else "", self.srid(), " optional" if self.__optional else "")

def is_simple(td):
    return isinstance(td, SimpleTypeDefinition) or (isinstance(td, ComplexTypeDefinition) and td.contentType()[0] == 'SIMPLE')
        
def is_derived_from(td, type_name):
    while td.name() != "anyType":
        if td.name() == type_name:
            return True
        td = td.baseTypeDefinition()
    return False

class Table:
    """A Table is a list of Columns or Links to other tables, a list of geometry columns and an id"""

    def __init__(self, name = '', fields = [], uid = None):
        self.__name = name
        self.__fields = {}
        for f in fields:
            self.__fields[f.name()] = f
        # uid column
        self.__uid_column = uid
        # last value for autoincremented id
        # A Table must have either a uid column or a autoincremented id
        # but not both
        self.__last_uid = None

    def name(self):
        return self.__name
    def set_name(self, name):
        self.__name = name
    def fields(self):
        return self.__fields
    def add_fields(self, fields):
        for f in fields:
            self.__fields[f.name()] = f
    def has_field(self, field_name):
        return self.__fields.has_key(field_name)
    def field(self, field_name):
        return self.__fields.get(field_name)
    
    def links(self):
        return [x for k, x in self.fields().iteritems() if isinstance(x, Link)]
    def columns(self):
        return [x for k, x in self.fields().iteritems() if isinstance(x, Column)]
    def geometries(self):
        return [x for k, x in self.fields().iteritems() if isinstance(x, Geometry)]
    def back_links(self):
        return [x for k, x in self.fields().iteritems() if isinstance(x, BackLink)]

    def uid_column(self):
        return self.__uid_column
    def set_uid_column(self, uid_column):
        self.__uid_column = uid_column

    def has_autoincrement_id(self):
        return self.__last_uid is not None
    def set_autoincrement_id(self):
        self.__uid_column = Column("id", auto_incremented = True)
        self.__fields['id'] = self.__uid_column
        self.__last_uid = 0
    def increment_id(self):
        self.__last_uid += 1
        return self.__last_uid
        
    def add_back_link(self, name, table):
        f = [x for x in table.back_links() if x.name() == name and x.table() == table]
        if len(f) == 0:
            self.__fields[name] = BackLink(name, table)
        
def print_etree(node, type_info_dict, indent = 0):
    ti = type_info_dict[node]
    td = ti.type_info().typeDefinition()
    print(" "*indent, no_prefix(node.tag), "type:", type_definition_name(td), end="")
    if ti.max_occurs() is None:
        print("[]")
    else:
        print()
    for n, t in ti.attribute_type_info_map().iteritems():
        print(" "*indent, "  @" + no_prefix(n), "type:", type_definition_name(t.attributeDeclaration().typeDefinition()))
    for child in node:
        print_etree(child, type_info_dict, indent + 2)

def simple_type_to_sql_type(td):
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


def _create_tables(node, table_name, type_info_dict, tables):
    """Creates or updates tables from a hierarchy of node
    :param node: the node
    :param table_name: the name of the table for this node
    :param type_info_dict: a dict to associate a node to its TypeInfo
    :param tables: the dict {table_name : Table} to be populated
    :returns: the created Table for the given node
    """
    if len(node.attrib) == 0 and len(node) == 0:
        # empty table
        return

    table = tables.get(table_name)
    if table is None:
        table = Table(table_name)
        tables[table_name] = table
    
    fields = []
    uid_column = None
    ti = type_info_dict[node]
    for attr_name in node.attrib.keys():
        if no_prefix(attr_name) == 'nil':
            continue
        au = ti.attribute_type_info_map()[attr_name]
        n_attr = no_prefix(attr_name)
        if not table.has_field(n_attr):
            c = Column(n_attr, ref_type = simple_type_to_sql_type(au.attributeDeclaration().typeDefinition()), optional = not au.required())
            fields.append(c)
            if n_attr == "id":
                uid_column = c

    if table.uid_column() is None:
        if uid_column is None:
            table.set_autoincrement_id()
        else:
            table.set_uid_column(uid_column)

    # in a sequence ?
    in_seq = False
    # type of the sequence
    seq_td = None
    for child in node:
        child_ti = type_info_dict[child]
        child_td = child_ti.type_info().typeDefinition()
        n_child_tag = no_prefix(child.tag)
        if child_ti.max_occurs() is None: # "*" cardinality
            if not (in_seq and seq_td == child_td):
                in_seq = True
                seq_td = child_td
        else:
            in_seq = False

        is_optional = child_ti.min_occurs() == 0 or child_ti.type_info().nillable()
        if is_simple(child_td):
            if not in_seq:
                # simple type, 1:1 cardinality => column
                if not table.has_field(n_child_tag):
                    fields.append(Column(n_child_tag, ref_type = simple_type_to_sql_type(child_td), optional = is_optional))
            else:
                # simple type, 1:N cardinality => table
                if not table.has_field(n_child_tag):
                    child_table_name = no_prefix(node.tag) + "_" + n_child_tag
                    child_table = Table(child_table_name, [Column("v", ref_type = simple_type_to_sql_type(child_td))])
                    tables[child_table_name] = child_table
                    fields.append(Link(n_child_tag, is_optional, child_ti.min_occurs(), child_ti.max_occurs(), simple_type_to_sql_type(child_td), child_table))
        elif is_derived_from(child_td, "AbstractGeometryType"):
            if not table.has_field(n_child_tag):
                gtype, gdim, gsrid = gml_geometry_type(child)
                fields.append(Geometry(n_child_tag, gtype, gdim, gsrid))
        else: # complex type
            has_id = any([1 for n in child.attrib.keys() if no_prefix(n) == "id"])
            if has_id:
                # shared table
                child_table_name = child_td.name() or no_prefix(node.tag) + "_t"
                _create_tables(child, child_table_name, type_info_dict, tables)
            else:
                child_table_name = no_prefix(node.tag) + "_" + n_child_tag
                _create_tables(child, child_table_name, type_info_dict, tables)
            child_table = tables.get(child_table_name)
            if child_table is not None: # may be None if the child_table is empty
                # create link
                if not table.has_field(n_child_tag):
                    sgroup = None
                    if child_ti.abstract_type_info() is not None:
                        sgroup = child_ti.abstract_type_info().name()
                    fields.append(Link(n_child_tag, is_optional, child_ti.min_occurs(), child_ti.max_occurs(), None, child_table, substitution_group = sgroup))

    table.add_fields(fields)

def _populate_tables(node, table_name, parent_id, type_info_dict, tables, tables_rows):
    if len(node.attrib) == 0 and len(node) == 0:
        # empty table
        return None
    print("Populate table", table_name)

    table = tables[table_name]
    # tables_rows is supposed to have an entry for each table
    table_rows = tables_rows[table_name]

    row = []
    table_rows.append(row)

    if parent_id is not None:
        row.append(parent_id)

    if table.has_autoincrement_id():
        current_id = table.increment_id()
        row.append(("id", current_id))
    else:
        current_id = None

    # attributes
    for attr_name, attr_value in node.attrib.iteritems():
        if no_prefix(attr_name) == 'nil':
            continue
        row.append((no_prefix(attr_name), attr_value))
        if no_prefix(attr_name) == "id":
            current_id = attr_value

    # number in the sequence
    seq_num = 0
    # tag of the sequence
    seq_tag = None
    for child in node:
        child_ti = type_info_dict[child]
        child_td = child_ti.type_info().typeDefinition()
        if child_ti.max_occurs() is None: # "*" cardinality
            if seq_num > 0 and seq_tag == child.tag:
                # if already in a sequence, increment seq_num
                seq_num += 1
            else:
                seq_num = 1
                seq_tag = child.tag
        else:
            seq_num = 0
        if is_simple(child_td):
            if seq_num == 0:
                # simple type, 1:1 cardinality => column
                v = child.text if child.text is not None else '' # FIXME replace by the default value ?
                row.append((no_prefix(child.tag), v))
            else:
                # simple type, 1:N cardinality => table
                v = child.text if child.text is not None else ''
                child_table_name = no_prefix(node.tag) + "_" + no_prefix(child.tag)
                child_table_rows = tables_rows[child_table_name]
                child_row = [(table_name + "_id", current_id), ("v", v)]
                child_table_rows.append(child_row)

        elif is_derived_from(child_td, "AbstractGeometryType"):
            # add geometry
            g_column = table.field(no_prefix(child.tag))
            g = ogr.CreateGeometryFromGML(ET.tostring(child))
            row.append((no_prefix(child.tag), ("GeomFromText('%s', %d)", g.ExportToWkt(), g_column.srid())))
        else:
            has_id = any([1 for n in child.attrib.keys() if no_prefix(n) == "id"])
            if has_id:
                # shared table
                child_table_name = child_td.name() or no_prefix(node.tag) + "_t"
            else:
                child_table_name = no_prefix(node.tag) + "_" + no_prefix(child.tag)
            if seq_num == 0:
                # 1:1 cardinality
                row_id = _populate_tables(child, child_table_name, None, type_info_dict, tables, tables_rows)
                row.append((no_prefix(child.tag)+"_id", row_id))
            else:
                # 1:N cardinality
                child_parent_id = (table_name + "_id", current_id)
                _populate_tables(child, child_table_name, child_parent_id, type_info_dict, tables, tables_rows)
    # return last inserted id
    print("End", table_name)
    return current_id

def populate_tables(root_node, type_info_dict, tables):
    """Returns values to insert in tables from a DOM document
    :param root_node: the root node
    :param  type_info_dict: the TypeInfo dict
    :param tables: the tables dict, returned by create_tables
    :returns: a dict {table_name: [ [(column_name, column_value), (...)]]
    """
    tables_rows = {}
    for n in tables.keys():
        tables_rows[n] = []
    _populate_tables(root_node, no_prefix(root_node.tag), None, type_info_dict, tables, tables_rows)
    return tables_rows

def create_or_update_tables(root_node, type_info_dict, tables = None):
    """Creates or updates table definitions from a document and its TypeInfo dict
    :param root_node: the root node
    :param type_info_dict: the TypeInfo dict
    :param tables: the existing table dict to update
    :returns: a dict {table_name : Table}
    """
    if tables is None:
        tables = {}
    table_name = no_prefix(root_node.tag)
    _create_tables(root_node, table_name, type_info_dict, tables)

    # create backlinks
    for name, table in tables.iteritems():
        for link in table.links():
            # only for links with a "*" cardinality
            if link.max_occurs() is None and link.ref_table() is not None:
                if not link.ref_table().has_field(link.name()):
                    link.ref_table().add_back_link(link.name(), table)
    return tables

def stream_sql_schema(tables):
    """Creates SQL(ite) table creation statements from a dict of Table
    :returns: a generator that yield a new SQL line
    """
    for name, table in tables.iteritems():
        stmt = u"CREATE TABLE " + name + u"(";
        columns = []
        for c in table.columns():
            if c.ref_type():
                l = c.name() + u" " + c.ref_type()
            else:
                l = c.name() + u" INT PRIMARY KEY"
            if not c.optional():
                l += u" NOT NULL"
            columns.append("  " + l)

        fk_constraints = []
        sub_groups = {}
        for link in table.links():
            if link.ref_table() is None or link.max_occurs() is None:
                continue
            if not link.optional() and not link.substitution_group():
                nullity = u" NOT NULL"
            else:
                nullity = u""

            # deal with substitution groups
            sgroup = link.substitution_group()
            if sgroup is not None:
                if not sub_groups.has_key(sgroup):
                    sub_groups[sgroup] = [link]
                else:
                    sub_groups[sgroup].append(link)

            id = link.ref_table().uid_column()
            if id is not None and id.ref_type() is not None:
                fk_constraints.append((link.name(), link.ref_table(), id.ref_type() + nullity))
            else:
                fk_constraints.append((link.name(), link.ref_table(), u"INT" + nullity))

        for bl in table.back_links():
            if bl.ref_table() is None:
                continue
            id = bl.ref_table().uid_column()
            if id is not None and id.ref_type() is not None:
                fk_constraints.append((bl.ref_table().name(), bl.ref_table(), id.ref_type()))
            else:
                fk_constraints.append((bl.ref_table().name(), bl.ref_table(), u"INT"))

        for n, table, type_str in fk_constraints:
            columns.append("  " + n + u"_id " + type_str)
        for n, table, type_str in fk_constraints:
            columns.append(u"  FOREIGN KEY({}_id) REFERENCES {}(id)".format(n, table.name()))

        # substitution group checks
        for sg, links in sub_groups.iteritems():
            columns.append(u"  CHECK (NOT(" + " AND ".join([l.name() + u"_id IS NULL" for l in links]) + "))")

        stmt += u",\n".join(columns) + u");"
        yield(stmt)

        for g in table.geometries():
            yield(u"SELECT AddGeometryColumn('{}', '{}', {}, '{}', '{}');".format(table.name(), g.name(), g.srid(), g.type(), "XY" if g.dimension() == 2 else "XYZ"))


def stream_sql_rows(tables_rows):
    def escape_value(v):
        if v is None:
            return u'null'
        if isinstance(v, (str,unicode)):
            return u"'" + unicode(v).replace("'", "''") + u"'"
        if isinstance(v, tuple):
            # ('GeomFromText('%s', %d)', 'POINT(...)')
            pattern = v[0]
            args = v[1:]
            return pattern % args
        else:
            return unicode(v)

    yield(u"PRAGMA foreign_keys = OFF;")
    for table_name, rows in tables_rows.iteritems():
        for row in rows:
            columns = [n for n,v in row if v is not None]
            values = [escape_value(v) for _,v in row if v is not None]
            yield(u"INSERT INTO {} ({}) VALUES ({});".format(table_name, ",".join(columns), ",".join(values)))
    yield(u"PRAGMA foreign_keys = ON;")

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
                nodes.append(child[0])
    else:
        # it seems to be an isolated feature
        nodes.append(root)
    return nodes

if len(sys.argv) < 3:
    print("Argument: [xsd_files] xml_file sqlite_file")
    exit(1)

xsd_files = sys.argv[1:-2]
xml_file = sys.argv[-2]
sqlite_file = sys.argv[-1]

if not os.path.exists("cache.bin"):
    uri_resolver = URIResolver("archive")

    doc = ET.parse(xml_file)
    if len(xsd_files) == 0:
        # try to download schemas
        root = doc.getroot()
        for an, av in root.attrib.iteritems():
            if no_prefix(an) == "schemaLocation":
                # assume the main schema is the first pair
                schemaLocation = av.split()[1]
                xsd_files = [uri_resolver.cache_uri(schemaLocation)]

    if len(xsd_files) == 0:
        print("No schema found, please specify them as arguments")
        exit(1)

    ns = parse_schemas(xsd_files, urlopen = lambda uri : uri_resolver.data_from_uri(uri))

    features = extract_features(doc)
    root = features[0]

    root_name = no_prefix(root.tag)
    root_type = ns.elementDeclarations()[root_name].typeDefinition()


    #print_etree(doc.getroot(), type_info_dict)

    print("Creating database schema ... ")

    tables = None
    tables_rows = None
    for idx, node in enumerate(features):
        print("+ Feature #{}/{}".format(idx+1, len(features)))
        type_info_dict = resolve_types(node, ns)
        tables = create_or_update_tables(node, type_info_dict, tables)
        trows = populate_tables(node, type_info_dict, tables)
        if tables_rows is None:
            tables_rows = trows
        else:
            for table, rows in trows.iteritems():
                if tables_rows.has_key(table):
                    tables_rows[table] += rows
                else:
                    tables_rows[table] = rows

    print("OK")

    if False:
        print("Writing cache file ... ")
        fo = open("cache.bin", "w")
        fo.write(pickle.dumps([tables, tables_rows, root_name]))
        fo.close()
else:
    print("Reading from cache file ... ")
    fi = open("cache.bin", "r")
    tables, tables_rows, root_name = pickle.loads(fi.read())

import pyspatialite.dbapi2 as db

if os.path.exists(sqlite_file):
    print("SQlite file already exists")
else:
    conn = db.connect(sqlite_file)
    cur = conn.cursor()
    print("Writing to SQLite file ... ")
    cur.execute("SELECT InitSpatialMetadata(1);")
    conn.commit()
    for line in stream_sql_schema(tables):
        cur.execute(line)
    conn.commit()
    for line in stream_sql_rows(tables_rows):
        cur.execute(line)
    conn.commit()
    print("OK")

qgis_file = sqlite_file.replace(".sqlite", ".qgs")
sys.path.append("/home/hme/src/QGIS/build/output/python")

from qgis.core import QgsApplication, QgsVectorLayer, QgsMapLayerRegistry, QgsProject, QgsRelation
from PyQt4.QtCore import QFileInfo

app = QgsApplication(sys.argv, True)
app.setPrefixPath("/home/hme/src/QGIS/build/output", True)
app.initQgis()

# load a layer for each table
layers = {}
root_group = QgsProject.instance().layerTreeRoot()
child_group = root_group.addGroup(root_name + u"'s linked tables")
child_group.setExpanded(False)
for table_name, table in tables.iteritems():
    geometry = table.geometries()[0].name() if len(table.geometries()) > 0 else None
    src = "dbname='{}' table=\"{}\"{} sql=".format(sqlite_file, table.name(), " (" + geometry + ")" if geometry is not None else "")
    l = QgsVectorLayer(src, table.name(), "spatialite")
    layers[table.name()] = l
    QgsMapLayerRegistry.instance().addMapLayer(l, False) # do not add to the legend
    if table_name == root_name:
        root_group.insertLayer(0, l)
    else:
        child_group.addLayer(l)
    

# declare relations 1:N
#  <relations>
#    <relation referencingLayer="EnvironmentalMonitoringFacility_reportedTo20160408154405050" referencedLayer="EnvironmentalMonitoringFacility20160408154405098" id="EnvironmentalMonitoringFacility_reportedTo20160408154405050_EnvironmentalMonitoringFacility_id_EnvironmentalMonitoringFacility20160408154405098_id" name="_reportedTo">
#      <fieldRef referencedField="id" referencingField="EnvironmentalMonitoringFacility_id"/>
#    </relation>
#  </relations>
# relations 1:1
#    <relation referencingLayer="EnvironmentalMonitoringFacility20160412165324596" referencedLayer="EnvironmentalMonitoringFacility_inspireId20160412165324591" id="EnvironmentalMonitoringFacility20160412165324596_inspireId_id_EnvironmentalMonitoringFacility_inspireId20160412165324591_id" name="qq">
#      <fieldRef referencedField="id" referencingField="inspireId_id"/>
#    </relation>


for table_name, table in tables.iteritems():
    for link in table.links():
        if link.max_occurs() is None:
            continue

        rel = QgsRelation()
        referencingLayer = layers[table.name()]
        referencingField = link.name() + "_id"
        referencedLayer = layers[link.ref_table().name()]
        referencedField = "id"
        rel.setReferencedLayer(referencedLayer.id())
        rel.setReferencingLayer(referencingLayer.id())
        rel.addFieldPair(referencingField, referencedField)
        rel.setRelationName(table.name() + "_" + link.name())
        rel.setRelationId(table.name() + "_" + link.name())
        if not rel.isValid():
            raise RuntimeError("not valid")
        QgsProject.instance().relationManager().addRelation(rel)
    for bl in table.back_links():
        # create a relation for this backlink
        rel = QgsRelation()
        referencingLayer = layers[table.name()]
        referencingField = bl.ref_table().name() + u"_id"
        referencedLayer = layers[bl.ref_table().name()]
        referencedField = "id"
        rel.setReferencedLayer(referencedLayer.id())
        rel.setReferencingLayer(referencingLayer.id())
        rel.addFieldPair(referencingField, referencedField)
        rel.setRelationName(table.name())
        rel.setRelationId(table.name())
        QgsProject.instance().relationManager().addRelation(rel)

        # set the layer's edit widget to "relation reference"
        #field_idx = referencingLayer.fieldNameIndex(referencingField)
        #print("********* field_idx", field_idx)
        #referencingLayer.editFormConfig().setWidgetType(field_idx, "RelationReference")

fi = QFileInfo(qgis_file)
QgsProject.instance().write(fi)
QgsApplication.exitQgis()

#        <edittype widgetv2type="RelationReference" name="EnvironmentalMonitoringFacility_id">
#          <widgetv2config OrderByValue="0" fieldEditable="1" ShowForm="0" Relation="_belongsTo" ReadOnly="0" MapIdentification="0" labelOnTop="0" AllowNULL="0"/>
#        </edittype>

#        <edittype widgetv2type="RelationReference" name="inspireId_id">
#          <widgetv2config OrderByValue="0" fieldEditable="1" AllowAddFeatures="0" ShowForm="1" Relation="EnvironmentalMonitoringFacility20160412165324596_inspireId_id_EnvironmentalMonitoringFacility_inspireId20160412165324591_id" ReadOnly="0" MapIdentification="0" labelOnTop="0" AllowNULL="0"/>
#        </edittype>

doc = ET.parse(qgis_file)
root = doc.getroot()
for child in root:
    if child.tag == "projectlayers":
        for layer in child:
            for field in layer:
                if field.tag == "layername":
                    layer_name = field.text
                if field.tag == "annotationform" or field.tag == "editform":
                    field.text = "."
                if field.tag == "editorlayout":
                    field.text = "tablayout"

            #raw_input()
            table = tables[layer_name]
            edittypes = ET.Element("edittypes")
            editform = ET.Element("attributeEditorForm")

            layer.append(edittypes)
            layer.append(editform)

            columns_container = ET.Element("attributeEditorContainer")
            columns_container.attrib["name"] = "Columns"
            columns_container.attrib["columnCount"] = "1"
            relations_container = ET.Element("attributeEditorContainer")
            relations_container.attrib["name"] = "Relations"
            relations_container.attrib["columnCount"] = "1"
            editform.append(columns_container)

            for idx, c in enumerate(table.columns()):
                edittype = ET.Element("edittype")
                edittype.attrib["widgetv2type"] = "TextEdit"
                edittype.attrib["name"] = c.name()
                wconfig = ET.Element("widgetv2config")
                wconfig.attrib["IsMultiline"] = "0"
                wconfig.attrib["fieldEditable"] = "0"
                wconfig.attrib["UseHtml"] = "0"
                wconfig.attrib["labelOnTop"] = "0"
                edittype.append(wconfig)
                edittypes.append(edittype)

                field = ET.Element("attributeEditorField")
                field.attrib["index"] = str(idx)
                field.attrib["name"] = c.name()
                columns_container.append(field)
                
            for link in table.links():
                if link.max_occurs() is None:
                    relation = ET.Element("attributeEditorRelation")
                    relation.attrib["relation"] = link.ref_table().name()
                    relation.attrib["name"] = link.name()
                    relations_container.append(relation)
                    continue
                print("link to", link.ref_table().name(), "via", link.name())
                edittype = ET.Element("edittype")
                edittype.attrib["widgetv2type"] = "RelationReference"
                edittype.attrib["name"] = link.name() + "_id"
                wconfig = ET.Element("widgetv2config")
                wconfig.attrib["OrderByValue"] = "0"
                wconfig.attrib["fieldEditable"] = "0"
                wconfig.attrib["ShowForm"] = "1" # embed the form
                wconfig.attrib["Relation"] = table.name() + "_" + link.name()
                wconfig.attrib["ReadOnly"] = "1"
                # allow map selection tools ?
                ref_layer = layers[link.ref_table().name()]
                has_geometry = len(link.ref_table().geometries()) > 0
                wconfig.attrib["MapIdentification"] = "1" if has_geometry else "0"
                wconfig.attrib["labelOnTop"] = "0"
                wconfig.attrib["AllowNULL"] = "1"
                edittype.append(wconfig)
                edittypes.append(edittype)

                field = ET.Element("attributeEditorField")
                field.attrib["index"] = str(idx)
                field.attrib["name"] = link.name() + "_id"
                columns_container.append(field)
                idx += 1

            if len(relations_container) > 0:
                editform.append(relations_container)

fo = open(qgis_file, "w")
fo.write(ET.tostring(root))
fo.close()


