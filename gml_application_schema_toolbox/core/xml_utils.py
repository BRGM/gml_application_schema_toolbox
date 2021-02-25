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


import io
import xml.etree.ElementTree as ET


def no_prefix(tag):
    """Remove the namespace prefix from the given name"""
    if tag.startswith("{"):
        return tag[tag.rfind("}") + 1 :]
    return tag


def prefix(tag):
    """Return the namespace prefix from the given name"""
    if tag.startswith("{"):
        return tag[1 : tag.rfind("}")]
    return ""


def no_ns(s):
    """Remove namespace prefix, except on attributes"""
    i = s.find(":")
    if i != -1 and "@" not in s[:i]:
        return s[i + 1 :]
    return s


def split_tag(tag):
    """Return a pair (ns prefix, tag) from a tag name"""
    if tag.startswith("{"):
        i = tag.rfind("}")
        return (tag[1:i], tag[i + 1 :])
    return ("", tag)


def remove_prefix(node):
    node.tag = no_prefix(node.tag)
    n = {}
    for k, v in node.attrib.items():
        n[no_prefix(k)] = v
    node.attrib = n
    for child in node:
        remove_prefix(child)


def resolve_xpath(node, xpath, ns_map=None):
    get_text = xpath.endswith("/text()")
    if get_text:
        xpath = xpath[0:-7]
    nodes = node.findall(xpath, ns_map)
    if get_text:
        nodes = [
            node.text if node is not None and node.text is not None else ""
            for node in nodes
        ]
    if len(nodes) == 0:
        return None if not get_text else ""
    elif len(nodes) == 1:
        return nodes[0]
    else:
        return nodes


def xml_root_tag(xml_file):
    """
    Return the root tag of an XML file
    :param xml_file: the input XML file
    :returns: root tag, as a string
    """
    for event, elem in ET.iterparse(xml_file, ["start"]):
        return elem.tag


def xml_parse(xml_file):
    """
    Parse an XML file, returns a tree of nodes and a dict of namespaces
    :param xml_file: the input XML file
    :returns: (doc, ns_map)
    """
    root = None
    ns_map = {}  # prefix -> ns_uri
    for event, elem in ET.iterparse(xml_file, ["start-ns", "start", "end"]):
        if event == "start-ns":
            ns_map[elem[0]] = elem[1]
        elif event == "start":
            if root is None:
                root = elem
    for prefix, uri in ns_map.items():
        ET.register_namespace(prefix, uri)

    return (ET.ElementTree(root), ns_map)


def xml_parse_from_string(s):
    return xml_parse(io.StringIO(s))
