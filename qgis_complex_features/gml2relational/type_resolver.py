import logging

from xml_utils import no_prefix, split_tag, prefix
from gml_utils import extract_features
from pyxb.xmlschema.structures import Schema, ElementDeclaration, ComplexTypeDefinition, Particle, ModelGroup, SimpleTypeDefinition, Wildcard, AttributeUse, AttributeDeclaration
from schema_parser import parse_schemas

import urllib2
import os
import xml.etree.ElementTree as ET

def _xsd_isinstance(type, base_type):
    """Returns True if the type (ComplexTypeDefinition) derives from the base_type"""
    while type.baseTypeDefinition() != type:
        if type == base_type:
            return True
        type = type.baseTypeDefinition()
    return False

def _find_element_declarations(obj, ns_map, min_occurs = 1, max_occurs = 1):
    """Returns a flatten list of (ElementDeclaration, abstract ElementDeclaration, minOccurs, maxOccurs) from the given node"""
    if isinstance(obj, ElementDeclaration):
        if isinstance(obj.typeDefinition(), ComplexTypeDefinition) and obj.typeDefinition().abstract():
            types = []
            # look for concrete types that derives from this abstract type
            for ns in ns_map.values():
                if not hasattr(ns,"elementDeclarations"):
                    continue
                for ed in ns.elementDeclarations().values():
                    if _xsd_isinstance(ed.typeDefinition(), obj.typeDefinition()):
                        types.append((ed, obj, min_occurs, max_occurs))
            return types
        return [(obj, obj, min_occurs, max_occurs)]        
    elif isinstance(obj, ComplexTypeDefinition):
        return _find_element_declarations(obj.contentType()[1], ns_map, min_occurs, max_occurs)
    elif isinstance(obj, Particle):
        return  _find_element_declarations(obj.term(), ns_map, obj.minOccurs(), obj.maxOccurs())
    elif isinstance(obj, ModelGroup):
        r = []
        for p in obj.particles():
            r += _find_element_declarations(p, ns_map, min_occurs, max_occurs)
        return r
    return []

def type_definition_name(td):
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
            type_name += "{}({})".format(std.name(), std.primitiveTypeDefinition().name())
        else:
            type_name += std.name()
    else:
        type_name = td.name() or "<unnamed_complex>"
    return type_name

class TypeInfo(object):

    def __init__(self, type_info, attribute_type_info_map, min_occurs = 1, max_occurs = 1, abstract_type_info = None):
        self.__type_info = type_info
        self.__abstract_type_info = abstract_type_info
        self.__attribute_type_info_map = attribute_type_info_map
        self.__min_occurs = min_occurs
        self.__max_occurs = max_occurs # None for unbounded

    def type_info(self):
        return self.__type_info

    def abstract_type_info(self):
        return self.__abstract_type_info

    def min_occurs(self):
        return self.__min_occurs

    def max_occurs(self):
        return self.__max_occurs

    def attribute_type_info_map(self):
        return self.__attribute_type_info_map

    def attribute_type_info(self, attribute_key):
        return self.__attribute_type_info_map[attribute_key]
        
def _resolve_types(etree_node, ns_map, declaration, abstract_declaration, min_occurs, max_occurs, type_info_dict):
    """
    :param etree_node: a node of a tree, following the etree API
    :param ns_map: namespace map
    :param cadrinality: cardinality of the node
    :param type_info_dict: a dict {Element : TypeInfo} to augment
    """
    node_ns, node_tag = split_tag(etree_node.tag)
    type_info_dict[etree_node] = TypeInfo(declaration, {}, min_occurs, max_occurs, abstract_declaration)

    if len(etree_node.attrib) > 0:
        attrs_uses = declaration.typeDefinition().attributeUses()
        for attr_name in etree_node.attrib.keys():
            ns_attr, n_attr_name = split_tag(attr_name)
            if ns_attr in ["http://www.w3.org/2001/XMLSchema-instance", 'http://www.w3.org/1999/xlink']:
                continue
            if ns_attr == "" and n_attr_name in ['nil', 'nilReason']:
                # special case where xsi namespace is not there (should be an error)
                continue
            attr_use = [au for au in attrs_uses if au.attributeDeclaration().name() == n_attr_name]
            if attr_use:
                type_info_dict[etree_node].attribute_type_info_map()[attr_name] = attr_use[0]
            else:
                raise RuntimeError("Can't find declaration for attribute {} in node {}".format(n_attr_name, etree_node.tag))

    if declaration.typeDefinition().name() == "anyType":
        # generic type
        for child in etree_node:
            ns, c_name = split_tag(child.tag)
            ed = ns_map[ns].elementDeclarations()[c_name]
            _resolve_types(child, ns_map, ed, None, 0, 1, type_info_dict)
    else:
        child_declarations = _find_element_declarations(declaration.typeDefinition(), ns_map)
        for child in etree_node:
            ns_name, c_name = split_tag(child.tag)
            possible_names = [c_name]
            ns = ns_map.get(ns_name)
            if ns is None:
                raise RuntimeError("Can't find namespace {}".format(ns_name))
            child_ed = ns.elementDeclarations().get(c_name)
            # look for substitution group
            if child_ed is not None and child_ed.substitutionGroupAffiliation() is not None and child_ed.substitutionGroupAffiliation().name() in [c[0].name() for c in child_declarations]:
                child_decl = [(child_ed, child_ed.substitutionGroupAffiliation(), 0, 1)]
            else:
                child_decl = [(ed, abs_ed, min_o, max_o) for ed, abs_ed, min_o, max_o in child_declarations if ed.name() == c_name]
            if len(child_decl) > 0:
                ed, abs_ed, min_o, max_o = child_decl[0]
                _resolve_types(child, ns_map, ed, abs_ed if abs_ed.abstract() else None, min_o, max_o, type_info_dict)
            else:
                raise RuntimeError("Unexpected element {} for node {}".format(c_name, node_tag))

def resolve_types(root_node, ns_map):
    """
    Augment the ElementTree with type informations for each element and each attribute.

    :param etree_node: An XML node following the ElementTree API
    :param ns_map: A PyXB's Namespace dict {namespace uri : namespace}
    :returns: a dict {Element : TypeInfo}
    """
    type_info_dict = {}
    root_ns, root_tag = split_tag(root_node.tag)
    decl = ns_map[root_ns].elementDeclarations()[root_tag]
    _resolve_types(root_node, ns_map, decl, None, 1, 1, type_info_dict)
    return type_info_dict

def uri_dirname(uri):
    if uri.startswith('http://'):
        return "http://" + os.path.dirname(uri[7:])
    return os.path.dirname(uri)

class URIResolver(object):
    def __init__(self, cachedir, logger, urlopener):
        self.__cachedir = cachedir
        self.__urlopener = urlopener
        self.__logger = logger

    def cache_uri(self, uri, parent_uri = '', lvl = 0):
        def mkdir_p(path):
            """Recursively create all subdirectories of a given path"""
            drive, fullpath = os.path.splitdrive(path)
            drive += os.sep
            dirs = fullpath.split(os.sep)
            if dirs[0] == '':
                p = drive
                dirs = dirs[1:]
            else:
                p = ''
            for d in dirs:
                p = os.path.join(p, d)
                if not os.path.exists(p):
                    os.mkdir(p)

        self.__logger.text((lvl,"Resolving schema {} ({})... ".format(uri, parent_uri)))

        if not uri.startswith('http://'):
            if not os.path.isabs(uri):
                # relative file name
                if not parent_uri.startswith('http://'):
                    uri = os.path.join(parent_uri, uri)
                else:
                    uri = parent_uri + "/" + uri.replace(os.sep, "/")
            if os.path.exists(uri):
                return uri

        base_uri = uri_dirname(uri)

        out_file_name = uri
        if uri.startswith('http://'):
            out_file_name = uri[7:].replace('/', os.sep)
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


def load_schemas_and_resolve_types(xml_file, archive_dir, xsd_files = None, urlopener = None, logger = None):
    if xsd_files is None:
        xsd_files = []
    if urlopener is None:
        urlopener = urllib2.urlopen
    if logger is None:
        logger = default_logger

    doc = ET.parse(xml_file)
    features = extract_features(doc)
    root = features[0]
    root_ns, root_name = split_tag(root.tag)

    uri_resolver = URIResolver(archive_dir, logger, urlopener)

    parent_uri = os.path.dirname(xml_file)

    if len(xsd_files) == 0:
        # try to download schemas
        root = doc.getroot()
        for an, av in root.attrib.iteritems():
            if no_prefix(an) == "schemaLocation":
                avs = av.split()
                for ns_name, ns_uri in zip(avs[0::2], avs[1::2]):
                    if ns_name not in ['http://www.opengis.net/wfs']:
                        xsd_files.append(uri_resolver.cache_uri(ns_uri, parent_uri))

    if len(xsd_files) == 0:
        raise RuntimeError("No schema found")

    ns_map = parse_schemas(xsd_files, urlopen = lambda uri : uri_resolver.data_from_uri(uri))

    ns = ns_map[root_ns]

    return [(node, resolve_types(node, ns_map)) for node in features]

    
