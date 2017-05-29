#   Copyright (C) 2016 BRGM (http:///brgm.fr)
#   Copyright (C) 2016 Oslandia <infos@oslandia.com>
#
#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Library General Public
#   License as published by the Free Software Foundation; either
#   version 2 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Library General Public License for more details.
#   You should have received a copy of the GNU Library General Public
#   License along with this library; if not, see <http://www.gnu.org/licenses/>.

from future import standard_library
standard_library.install_aliases()
# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
import io

def no_prefix(tag):
    """Remove the namespace prefix from the given name"""
    if tag.startswith('{'):
        return tag[tag.rfind('}')+1:]
    return tag

def prefix(tag):
    """Return the namespace prefix from the given name"""
    if tag.startswith('{'):
        return tag[1:tag.rfind('}')]
    return ""

def split_tag(tag):
    """Return a pair (ns prefix, tag) from a tag name"""
    if tag.startswith('{'):
        i = tag.rfind('}')
        return (tag[1:i], tag[i+1:])
    return ("", tag)

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
        for an, av in node.attrib.items():
            if no_prefix(an) == part[1:]:
                return av

    if part == no_prefix(node.tag):
        return resolve_xpath(node, '/'.join(path[1:]))
    
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

def xml_parse(xml_file):
    """
    Parse an XML file, returns a tree of nodes and a dict of namespaces
    :param xml_file: the input XML file
    :returns: (doc, ns_map)
    """
    root = None
    ns_map = {} # prefix -> ns_uri
    for event, elem in ET.iterparse(xml_file, ['start-ns', 'start', 'end']):
        if event == 'start-ns':
            # elem = (prefix, ns_uri)
            ns_map[elem[0]] = elem[1]
        elif event == 'start':
            if root is None:
                root = elem
    for prefix, uri in ns_map.items():
        ET.register_namespace(prefix, uri)
        
    return (ET.ElementTree(root), ns_map)

def xml_parse_from_string(s):
    return xml_parse(io.StringIO(s))
