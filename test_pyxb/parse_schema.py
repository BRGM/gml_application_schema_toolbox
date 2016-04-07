#!/usr/bin/env python

from __future__ import print_function
import logging
logging.basicConfig()

import sys
sys.path = ['/home/hme/src/pyxb'] + sys.path
print(sys.path)

from pyxb.xmlschema.structures import Schema, ElementDeclaration, ComplexTypeDefinition, Particle, ModelGroup, SimpleTypeDefinition, Wildcard, AttributeUse, AttributeDeclaration

from schema_parser import parse_schemas
from type_resolver import resolve_types, no_prefix, type_definition_name

import os
import sys
import urllib2

def mkdir_p(path):
    """Recursively create all subdirectories of a given path"""
    dirs = path.split('/')
    p = ""
    for d in dirs:
        p = os.path.join(p, d)
        if not os.path.exists(p):
            os.mkdir(p)

class URIResolver(object):
    def __init__(self, cachedir):
        self.__cachedir = cachedir

    def data_from_uri(self, uri):
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
        f = open(out_file_name)
        print("OK")
        return f.read()

def is_simple(td):
    return isinstance(td, SimpleTypeDefinition) or (isinstance(td, ComplexTypeDefinition) and td.contentType()[0] == 'SIMPLE')
        
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

    def __init__(self, name, min_occurs, max_occurs, ref_type, ref_table = None):
        self.__name = name
        self.__min_occurs = min_occurs
        self.__max_occurs = max_occurs
        self.__ref_type = ref_type
        self.__ref_table = ref_table

    def name(self):
        return self.__name
    def ref_type(self):
        return self.__ref_type
    def ref_table(self):
        return self.__ref_table
    def set_ref_table(self, ref_table):
        self.__ref_table = ref_table
    def min_occurs(self):
        return self.__min_occurs
    def max_occurs(self):
        return self.__max_occurs

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

    def __init__(self, name, optional = False):
        self.__name = name
        self.__optional = optional

    def name(self):
        return self.__name
    def optional(self):
        return self.__optional
    def __repr__(self):
        return "Geometry<{}{}>".format(self.__name, " optional" if self.__optional else "")

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
        self.__fields = list(fields)
        self.__uid_column = uid

    def name(self):
        return self.__name
    def set_name(self, name):
        self.__name = name
    def fields(self):
        return self.__fields
    def links(self):
        return [x for x in self.__fields if isinstance(x, Link)]
    def columns(self):
        return [x for x in self.__fields if isinstance(x, Column)]
    def geometries(self):
        return [x for x in self.__fields if isinstance(x, Geometry)]
    def back_links(self):
        return [x for x in self.__fields if isinstance(x, BackLink)]
    def uid_column(self):
        return self.__uid_column

    def add_back_link(self, name, table):
        f = [x for x in table.back_links() if x.name() == name and x.table() == table]
        if len(f) == 0:
            self.__fields.append(BackLink(name, table))
        
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
        raise RuntimeError("Not simple type" + td)
    type_map = {'string': 'TEXT',
                'integer' : 'INT',
                'boolean' : 'BOOLEAN',
                'NilReasonType' : 'TEXT',
                'anyURI' : 'TEXT'
    }
    return type_map.get(type_name) or type_name

def _create_tables(node, parent_node, type_info_dict, tables):
    """Creates tables from a hierarchy of node
    :param node: the node
    :param parent_node: the parent_node of the node, or None
    :param type_info_dict: a dict to associate a node to its TypeInfo
    :param tables: the dict {table_name : Table} to be populated
    :returns: the created Table for the given node
    """
    if len(node.attrib) == 0 and len(node) == 0:
        # empty table
        return None
    
    fields = []
    uid_column = None
    ti = type_info_dict[node]
    for attr_name in node.attrib.keys():
        if not ti.attribute_type_info_map().has_key(attr_name):
            continue
        au = ti.attribute_type_info_map()[attr_name]
        c = Column(no_prefix(attr_name), ref_type = au.attributeDeclaration().typeDefinition(), optional = not au.required())
        fields.append(c)
        if no_prefix(attr_name) == "id":
            uid_column = c
    if uid_column is None:
        uid_column = Column("id", auto_incremented = True)
        fields.append(uid_column)

    # number in the current sequence, 0 if not in a sequence
    seq_num = 0
    # type of the sequence
    seq_td = None
    for child in node:
        child_ti = type_info_dict[child]
        child_td = child_ti.type_info().typeDefinition()
        if child_ti.max_occurs() is None: # "*" cardinality
            if seq_num > 0 and seq_td == child_td:
                # if already in a sequence, increment seq_num
                seq_num += 1
                continue
            else:
                seq_num = 1
                seq_td = child_td
        else:
            seq_num = 0
        if seq_num == 0 and is_simple(child_td):
            fields.append(Column(no_prefix(child.tag), ref_type = child_td, optional = child_ti.min_occurs() == 0))
        elif seq_num > 0 and is_simple(child_td):
            table_name = no_prefix(node.tag) + "_" + no_prefix(child.tag)
            table = Table(table_name, [Column("v", ref_type=child_td)])
            tables[table_name] = table
            fields.append(Link(no_prefix(child.tag), child_ti.min_occurs(), child_ti.max_occurs(), child_td, table))
        elif is_derived_from(child_td, "AbstractGeometryType"):
            fields.append(Geometry(no_prefix(child.tag)))
        else:
            has_id = any([1 for n in child.attrib.keys() if no_prefix(n) == "id"])
            if has_id:
                # shared table
                table_name = child_td.name() or no_prefix(node.tag) + "_t"
                if not tables.has_key(table_name):
                    tables[table_name] = _create_tables(child, node, type_info_dict, tables)
                table = tables[table_name]
            else:
                table_name = no_prefix(node.tag) + "_" + no_prefix(child.tag)
                table = _create_tables(child, node, type_info_dict, tables)
            # create link
            fields.append(Link(no_prefix(child.tag), child_ti.min_occurs(), child_ti.max_occurs(), child_td, table))

    if parent_node is not None:
        table_name = no_prefix(parent_node.tag) + "_" + no_prefix(node.tag)
    else:
        table_name = no_prefix(node.tag)
    t = Table(table_name, fields, uid_column)
    tables[table_name] = t
    return t


def create_tables(doc, type_info_dict):
    """Creates table definitions from a document and its TypeInfo dict
    :param doc: the document
    :param type_info_dict: the TypeInfo dict
    :returns: a dict {table_name : Table}
    """
    tables = {}
    table = _create_tables(doc.getroot(), None, type_info_dict, tables)

    # create backlinks
    for name, table in tables.iteritems():
        for link in table.links():
            # only for links with a "*" cardinality
            if link.max_occurs() is None and link.ref_table() is not None:
                link.ref_table().add_back_link(link.name(), table)
    return tables

def create_sql_schema(tables):
    """Creates SQL(ite) table creation statements from a dict of Table
    :returns: a generator that yield a new SQL line
    """
    for name, table in tables.iteritems():
        yield("CREATE TABLE " + name + "(")
        columns = []
        for c in table.columns():
            if c.ref_type():
                l = c.name() + " " + simple_type_to_sql_type(c.ref_type())
            else:
                l = c.name() + " INT PRIMARY KEY"
            if not c.optional():
                l += " NOT NULL"
            columns.append(l)

        for g in table.geometries():
            columns.append(g.name() + " GEOMETRY")

        fk_constraints = []
        for link in table.links():
            if link.ref_table() is None or link.max_occurs() is None:
                continue
            if link.min_occurs() > 0:
                nullity = " NOT NULL"
            else:
                nullity = ""

            id = link.ref_table().uid_column()
            if id is not None and id.ref_type() is not None:
                fk_constraints.append((link.name(), link.ref_table(), simple_type_to_sql_type(id.ref_type()) + nullity))
            else:
                fk_constraints.append((link.name(), link.ref_table(), "INT" + nullity))

        for bl in table.back_links():
            if bl.ref_table() is None:
                continue
            id = bl.ref_table().uid_column()
            if id is not None and id.ref_type() is not None:
                fk_constraints.append((bl.ref_table().name(), bl.ref_table(), simple_type_to_sql_type(id.ref_type())))
            else:
                fk_constraints.append((bl.ref_table().name(), bl.ref_table(), "INT"))

        for n, table, type_str in fk_constraints:
            columns.append(n + "_id " + type_str)
        for n, table, type_str in fk_constraints:
            columns.append("FOREIGN KEY({}_id) REFERENCES {}(id)".format(n, table.name()))

        yield(",\n".join(columns))
        yield(");")

if len(sys.argv) < 3:
    print("Argument: xsd_file xml_file")
    exit(1)

xsd_files = sys.argv[1:-1]
xml_file = sys.argv[-1]
    
uri_resolver = URIResolver("archive")

ns = parse_schemas(xsd_files, urlopen = lambda uri : uri_resolver.data_from_uri(uri))

import xml.etree.ElementTree as ET
doc = ET.parse(xml_file)

root_name = no_prefix(doc.getroot().tag)
root_type = ns.elementDeclarations()[root_name].typeDefinition()

type_info_dict = resolve_types(doc, ns)

print_etree(doc.getroot(), type_info_dict)

tables = create_tables(doc, type_info_dict)
for line in create_sql_schema(tables):
    print(line)

    
