# -*- coding: utf-8 -*-

import os

from qgis.PyQt import uic

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'help_panel.ui'))

class HelpPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(HelpPanel, self).__init__(parent)
        self.setupUi(self)
