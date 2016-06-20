#!/usr/bin/env python
# -*- coding: utf-8 -*-
def name():
    return u"QGIS GML Application Schema Toolbox"
def description():
    return u"QGIS GML Application Schema Toolbox"
def version():
    return u"0.8.0"
def icon():
    return "icon.png"
def qgisMinimumVersion():
    return u"2.14"
def qgisMaximumVersion():
    return u"2.99"
def classFactory(iface):
    from main import MainPlugin
    return MainPlugin(iface)
