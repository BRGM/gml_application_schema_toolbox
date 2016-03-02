#!/usr/bin/env python
# -*- coding: utf-8 -*-
def name():
    return "Complex Features for QGIS"
def description():
    return "Complex Features for QGIS"
def version():
    return "Version 1.0"
def icon():
    return "icon.png"
def qgisMinimumVersion():
    return "1.8"
def qgisMaximumVersion():
    return "2.99"
def classFactory(iface):
    from main import MainPlugin
    return MainPlugin(iface)
