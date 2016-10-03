"""
/**
 *   Copyright (C) 2016 BRGM (http:///brgm.fr)
 *   Copyright (C) 2016 Oslandia <infos@oslandia.com>
 *
 *   This library is free software; you can redistribute it and/or
 *   modify it under the terms of the GNU Library General Public
 *   License as published by the Free Software Foundation; either
 *   version 2 of the License, or (at your option) any later version.
 *
 *   This library is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *   Library General Public License for more details.
 *   You should have received a copy of the GNU Library General Public
 *   License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */
"""
from future import standard_library
standard_library.install_aliases()
# -*- coding: utf-8 -*-
import urllib.request, urllib.error, urllib.parse

# This is getting hacky ...
# The uri normalization function has problems with Windows path
# (it probably should not be called with plain path, but with file:// url ...)
# So we monkey patch it ...
oldNormalizeLocation = None
def myNormalizeLocation (uri, parent_uri=None, prefix_map=None):
    if uri is not None and parent_uri is not None and len(parent_uri) > 1 and parent_uri[1] == ':':
        # may be a Windows drive letter
        abs_uri = oldNormalizeLocation(uri, "file://" + parent_uri.replace("\\", "/"), prefix_map)
        if abs_uri.startswith('file://'):
            return abs_uri[7:]
        return abs_uri
    return oldNormalizeLocation(uri, parent_uri, prefix_map)
        
def parse_schemas(schema_files, urlopen = urllib.request.urlopen):
    """
    Returns a pyxb Namespace for the given schemas.
    Every dependent schemas will be downloaded thanks to the urlopen function passed in argument.
    :param schema_files: list of schema filename
    :param urlopen: function that takes an URL and returns a file-like object
    :returns: a dict {namespace_uri: pyxb Namespace that is resolved}
    """
    import pyxb.binding.generate
    import pyxb.utils.utility

    try:
        # monkey patch DataFromURI to use our own function
        # so that we can easily manage cache, proxies, and so on
        old_DataFromURI = pyxb.utils.utility.DataFromURI
        pyxb.utils.utility.DataFromURI = lambda uri, archive_directory = None : urlopen(uri)
        
        global oldNormalizeLocation
        oldNormalizeLocation = pyxb.utils.utility.NormalizeLocation
        pyxb.utils.utility.NormalizeLocation = myNormalizeLocation
        
        generator = pyxb.binding.generate.Generator()
        # default options
        parser = generator.optionParser()
        (options, args) = parser.parse_args(args = schema_files)
        generator.applyOptionValues(options, schema_files)
        # call to moduleRecords and ignore the returned value
        # we only need to make sure the namespace is validated and "resolved"
        generator.moduleRecords()
    except pyxb.SchemaValidationError as e:
        raise RuntimeError("When parsing {} - {}".format(schema_files, e.args))
    finally:
        # restore the initial DataFromURI
        pyxb.utils.utility.DataFromURI = old_DataFromURI
        pyxb.utils.utility.NormalizeLocation = oldNormalizeLocation

    schemas = generator.schemas()
    ns_map = {}
    for schema in schemas:
        ns = schema.targetNamespace()

        # must call resolve to have a walkable schema tree
        ns.resolveDefinitions()
        ns_map[ns.uri()] = ns

        for sub_ns in ns.AvailableNamespaces():
            if not any([sub_ns.uri().startswith(u) for u in ('http://www.w3.org/2000/xmlns/',
                                                             'http://www.w3.org/2001/XMLSchema',
                                                             'http://www.w3.org/XML',
                                                             'http://www.w3.org/1999/xhtml')]):
                ns_map[sub_ns.uri()] = sub_ns

    return ns_map
