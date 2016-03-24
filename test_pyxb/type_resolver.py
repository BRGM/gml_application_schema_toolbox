from pyxb.xmlschema.structures import Schema, ElementDeclaration, ComplexTypeDefinition, Particle, ModelGroup, SimpleTypeDefinition, Wildcard, AttributeUse, AttributeDeclaration

def _xsd_isinstance(type, base_type):
    """Returns True if the type (ComplexTypeDefinition) derives from the base_type"""
    while type.baseTypeDefinition() != type:
        if type == base_type:
            return True
        type = type.baseTypeDefinition()
    return False

def _find_element_declarations(obj):
    """Returns a flatten list of ElementDeclaration from the given node"""
    if isinstance(obj, ElementDeclaration):
        if isinstance(obj.typeDefinition(), ComplexTypeDefinition) and obj.typeDefinition().abstract():
            types = []
            # look for concrete types that derives from this abstract type
            for n, ed in obj.targetNamespace().elementDeclarations().iteritems():
                if _xsd_isinstance(ed.typeDefinition(), obj.typeDefinition()):
                    types.append(ed)
            return types
        return [obj]
    elif isinstance(obj, ComplexTypeDefinition):
        return _find_element_declarations(obj.contentType()[1])
    elif isinstance(obj, Particle):
        return _find_element_declarations(obj.term())
    elif isinstance(obj, ModelGroup):
        r = []
        for p in obj.particles():
            r += _find_element_declarations(p)
        return r
    return []

def no_prefix(tag):
    """Remove the namespace prefix from the given name"""
    if tag.startswith('{'):
        return tag[tag.rfind('}')+1:]
    return tag

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

    def __init__(self, type_info, attribute_type_info_map):
        self.__type_info = type_info
        self.__attribute_type_info_map = attribute_type_info_map

    def type_info(self):
        return self.__type_info

    def attribute_type_info_map(self):
        return self.__attribute_type_info_map

    def attribute_type_info(self, attribute_key):
        return self.__attribute_type_info_map[attribute_key]
        
def _resolve_types(etree_node, declaration, type_info_dict):
    """
    :param etree_node: a node of a tree, following the etree API
    :param declaration: ElementDeclaration of the node
    :param type_info_dict: a dict {Element : TypeInfo} to augment
    """
    type_info_dict[etree_node] = TypeInfo(declaration, {})

    if len(etree_node.attrib) > 0:
        attrs_decl = [au.attributeDeclaration() for au in declaration.typeDefinition().attributeUses()]
        for attr_name in etree_node.attrib.keys():
            n_attr_name = no_prefix(attr_name)
            if n_attr_name == 'nil':
                continue
            attr_decl = [ad for ad in attrs_decl if ad.name() == n_attr_name]
            if attr_decl:
                type_info_dict[etree_node].attribute_type_info_map()[attr_name] = attr_decl[0]
            else:
                raise RuntimeError("Can't find declaration for attribute {}", n_attr_name)

    child_declarations = _find_element_declarations(declaration.typeDefinition())
    for child in etree_node:
        c_name = no_prefix(child.tag)
        child_decl = [ed for ed in child_declarations if ed.name() == c_name]
        if len(child_decl) > 0:
            _resolve_types(child, child_decl[0], type_info_dict)
        else:
            raise RuntimeError("Can't find declaration for element {}", c_name)

def resolve_types(etree_doc, namespace):
    """
    Augment the ElementTree document with type informations for each element and each attribute.

    :param etree_doc: An XML document following the ElementTree API
    :param namespace: A PyXB's Namespace
    :returns: a dict {Element : TypeInfo}
    """
    root_node = etree_doc.getroot()
    type_info_dict = {}
    _resolve_types(root_node, namespace.elementDeclarations()[no_prefix(root_node.tag)], type_info_dict)
    return type_info_dict

