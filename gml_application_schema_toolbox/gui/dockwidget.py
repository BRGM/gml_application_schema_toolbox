# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GmlasPluginDockWidget
                                 A QGIS plugin
 GMLAS Plugin
                             -------------------
        begin                : 2016-09-21
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Arnaud Morvan - www.camptocamp.com
        email                : arnaud.morvan@camptocamp.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from qgis.PyQt import uic

from gml_application_schema_toolbox.gui.load_panel import LoadWfs2Panel

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'dockwidget.ui'))


class DockWidget(BASE, WIDGET):

    def __init__(self, parent=None):
        super(DockWidget, self).__init__(parent)
        self.setupUi(self)

        self.load_panel = LoadWfs2Panel()
        self.scroll_area.setWidget(self.load_panel)
