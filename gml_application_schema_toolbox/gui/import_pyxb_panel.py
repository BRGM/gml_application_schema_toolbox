# -*- coding: utf-8 -*-

import os
from qgis.PyQt import uic

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'import_pyxb_panel.ui'))


class ImportPyxbPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(ImportPyxbPanel, self).__init__(parent)
        self.setupUi(self)
