#!/usr/bin/env python

from __future__ import print_function
import logging
logging.basicConfig()

import sys
sys.path = ['/home/hme/src/pyxb'] + sys.path
print(sys.path)

from pyxb.xmlschema.structures import Schema, ElementDeclaration, ComplexTypeDefinition, Particle, ModelGroup, SimpleTypeDefinition, Wildcard, AttributeUse, AttributeDeclaration
from pyxb.namespace.resolution import ResolveSiblingNamespaces
from pyxb.utils.utility import UniqueIdentifier
from pyxb.utils import domutils
import pyxb.utils.utility

if len(sys.argv) < 3:
    print("Argument: xsd_file xml_file")
    exit(1)

from lxml import etree

import urllib2
import os

def print_tree(obj):
    stack = [(obj,0)]
    while len(stack) > 0:
        #print("stack", stack)
        obj, lvl = stack[0]

        new_objs = None
        #print(" " * lvl, obj.__class__.__name__, " ",end="")
        if isinstance(obj, ElementDeclaration):
            print(" "*lvl,"ElementDeclaration <" + obj.name() + ">", end="")
            if obj.typeDefinition():
                print("typeDefinition ->")
                new_objs = [(obj.typeDefinition(), lvl+2)]
            else:
                print
        elif isinstance(obj, ComplexTypeDefinition):
            print(" "*lvl,"ComplexType")
            new_objs = []
            if len(obj.attributeUses()) > 0:
                new_objs = [(au, lvl+2) for au in obj.attributeUses()]
                
            contentType = obj.contentType()
            if contentType:
                if isinstance(contentType, tuple):
                    new_objs += [(contentType[1], lvl+2)]
        elif isinstance(obj, SimpleTypeDefinition):
            print(" "*lvl,"SimpleType", obj.name())
        elif isinstance(obj, Particle):
            if obj.minOccurs() == 1 and obj.maxOccurs() == 1 and obj.term():
                new_objs = [(obj.term(), lvl)]
            else:
                print(" "*lvl, "Particle", obj.minOccurs(), "-", obj.maxOccurs(), end="")
                if obj.term():
                    print("term ->")
                    new_objs = [(obj.term(), lvl+2)]
                else:
                    print()
        elif isinstance(obj, ModelGroup):
            if len(obj.particles()) == 1:
                new_objs = [(obj.particles()[0], lvl)]
            else:
                print(" "*lvl, obj.compositorToString())
                new_objs = [(o, lvl+2) for o in obj.particles()]
        elif isinstance(obj, Wildcard):
            print(" " * lvl, "Wildcard")
        elif isinstance(obj, AttributeUse):
            print(" " * lvl, "AttributeUse", "required", obj.required())
            new_objs = [(obj.attributeDeclaration(), lvl+2)]
        elif isinstance(obj, AttributeDeclaration):
            print(" " * lvl, "AttributeDeclaration", obj.name())
            new_objs = [(obj.typeDefinition(), lvl+2)]
        else:
            print(" " * lvl, obj.__class__.__name__, "???")

        if new_objs:
            stack = new_objs + stack[1:]
        else:
            stack = stack[1:]
                
    
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

# monkey patch pyxb.utils.utility.DataFromURI
uri_resolver = URIResolver("archive")
pyxb.utils.utility.DataFromURI = lambda uri, archive_directory = None : uri_resolver.data_from_uri(uri)

import pyxb.binding.generate
generator = pyxb.binding.generate.Generator()
# default options
parser = generator.optionParser()
schema_files = sys.argv[1:-1]
xml_file = sys.argv[-1]
(options, args) = parser.parse_args(args = schema_files)
generator.applyOptionValues(options, schema_files)
# call to moduleRecords and ignore the returned value
# we only need to make sure the namespace is "resolved"
generator.moduleRecords()

schema = generator.schemas()[0]
ns = schema.targetNamespace()

# must call resolve to have a walkable schema tree
ns.resolveDefinitions()

def xsd_isinstance(type, base_type):
    while type.baseTypeDefinition() != type:
        if type == base_type:
            return True
        type = type.baseTypeDefinition()
    return False

def find_element_declarations(obj):
    if isinstance(obj, ElementDeclaration):
        if isinstance(obj.typeDefinition(), ComplexTypeDefinition) and obj.typeDefinition().abstract():
            #print("abstract type", obj.typeDefinition())
            types = []
            # look for concrete types that derives from this abstract type
            for n, ed in obj.targetNamespace().elementDeclarations().iteritems():
                if xsd_isinstance(ed.typeDefinition(), obj.typeDefinition()):
                    types.append(ed)
            return types
        return [obj]
    elif isinstance(obj, ComplexTypeDefinition):
        return find_element_declarations(obj.contentType()[1])
    elif isinstance(obj, Particle):
        return find_element_declarations(obj.term())
    elif isinstance(obj, ModelGroup):
        r = []
        for p in obj.particles():
            r += find_element_declarations(p)
        return r
    return []

def noPrefix(tag):
    if tag.startswith('{'):
        return tag[tag.rfind('}')+1:]
    return tag

def resolve_types(dom_node, declaration):
    """
    Augment the DOM tree nodes with their type information.
    Two new members will be added to each Element instance:
      * type_info that links to the ElementDeclaration
      * attrib_type_info: a dict that link to an AttributeDeclaration for each attribute

    :param dom_node: a node of a DOM tree, following the etree API
    :param declaration: ElementDeclaration of the DOM node
    """
    dom_node.type_info = declaration
    if not hasattr(dom_node, "attrib_type_info"):
        dom_node.attrib_type_info = {}

    if len(dom_node.attrib) > 0:
        attrs_decl = [au.attributeDeclaration() for au in declaration.typeDefinition().attributeUses()]
        for attr_name in dom_node.attrib.keys():
            n_attr_name = noPrefix(attr_name)
            if n_attr_name == 'nil':
                continue
            attr_decl = [ad for ad in attrs_decl if ad.name() == n_attr_name]
            if attr_decl:
                dom_node.attrib_type_info[attr_name] = attr_decl[0]
            else:
                raise RuntimeError("Can't find declaration for attribute {}", n_attr_name)

    child_declarations = find_element_declarations(declaration.typeDefinition())
    for child in dom_node:
        c_name = noPrefix(child.tag)
        child_decl = [ed for ed in child_declarations if ed.name() == c_name]
        if len(child_decl) > 0:
            resolve_types(child, child_decl[0])
        else:
            raise RuntimeError("Can't find declaration for element {}", c_name)

if False:
    f = open(xml_file)
    doc = domutils.StringToDOM(f.read())
    root_node = doc.childNodes[0]

import xml.etree.ElementTree as ET
doc = ET.parse(xml_file)
root_node = doc.getroot()

resolve_types(root_node, ns.elementDeclarations()[noPrefix(root_node.tag)])

def print_dom(node, indent = 0):
    print(" "*indent, noPrefix(node.tag), "type:", node.type_info)
    for n, t in node.attrib_type_info.iteritems():
        print(" "*indent, "  @" + noPrefix(n), "type:", t)
    for child in node:
        print_dom(child, indent + 2)

print_dom(root_node)
