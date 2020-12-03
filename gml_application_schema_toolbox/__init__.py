#!/usr/bin/env python
"""
/**
 *   Copyright (C) 2016 BRGM (http://brgm.fr)
 *   Copyright (C) 2016 Oslandia <infos@oslandia.com>
 *   Copyright (C) 2016 Camptocamp (http://camptocamp.com)
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


def name():
    return "QGIS GML Application Schema Toolbox"


def description():
    return "QGIS GML Application Schema Toolbox"


def version():
    return "1.2.0"


def icon():
    return "icon.png"


def qgisMinimumVersion():
    return "2.99"


def qgisMaximumVersion():
    return "3.99"


def classFactory(iface):
    from .main import MainPlugin

    return MainPlugin(iface)
