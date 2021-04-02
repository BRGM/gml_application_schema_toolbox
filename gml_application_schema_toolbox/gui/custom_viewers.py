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


import sys

__custom_viewers = None


def get_custom_viewers():
    global __custom_viewers

    if __custom_viewers is not None:
        # viewers already loaded
        return __custom_viewers
    __custom_viewers = {}

    # introspect the viewers module
    module = sys.modules["gml_application_schema_toolbox.viewers"]
    for klass in dir(module):
        if klass.startswith("__"):
            continue
        k = getattr(module, klass)
        if hasattr(k, "xml_tag"):
            r = k.xml_tag()
            fltr = None
            if isinstance(r, tuple):
                tag, fltr = r
            else:
                tag = r
            __custom_viewers[tag] = (k, fltr)

    return __custom_viewers
