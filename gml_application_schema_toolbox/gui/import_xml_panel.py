# -*- coding: utf-8 -*-

#   Copyright (C) 2017 BRGM (http:///brgm.fr)
#   Copyright (C) 2017 Oslandia <infos@oslandia.com>
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

import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSlot, QVariant
from qgis.PyQt.QtWidgets import QFileDialog, QComboBox, QTableWidgetItem

from qgis.core import QgsProject, QgsEditFormConfig, QgsEditorWidgetSetup

from ..core.settings import settings
from ..core.load_gml_as_xml import load_as_xml_layer
from ..gui import qgis_form_custom_widget
from ..gui.progress_bar import ProgressBarLogger

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'import_xml_panel.ui'))


class ImportXmlPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(ImportXmlPanel, self).__init__(parent)
        self.setupUi(self)

        self.attributeTable.selectionModel().selectionChanged.connect(self.onSelectMapping)

    @pyqtSlot()
    def on_gmlPathButton_clicked(self):
        gml_path = settings.value("gml_path", "")
        path, filter = QFileDialog.getOpenFileName(self,
                                                   self.tr("Open GML file"),
                                                   gml_path,
                                                   self.tr("GML files (*.gml *.xml)"))
        if path:
            settings.setValue("gml_path", os.path.dirname(path))
            self.gmlPathLineEdit.setText(path)

    @pyqtSlot()
    def on_importButton_clicked(self):
        gml_path = self.gmlPathLineEdit.text()

        # get attribute mapping
        mapping = {}
        for i in range(self.attributeTable.rowCount()):
            attr = self.attributeTable.item(i, 0).text()
            xpath = self.attributeTable.item(i, 2).text()
            combo = self.attributeTable.cellWidget(i, 1)
            type = combo.itemData(combo.currentIndex())
            mapping[attr] = (xpath, type)

        # add a progress bar during import
        # mediaMonitored/@title
        lyr = load_as_xml_layer(gml_path,
                                is_remote = gml_path.startswith('http://') or gml_path.startswith('https://'),
                                attributes = mapping,
                                logger = ProgressBarLogger("Importing features ..."))

        # install an XML tree widget
        qgis_form_custom_widget.install_xml_tree_on_feature_form(lyr)

        # id column
        lyr.setEditorWidgetSetup(0, QgsEditorWidgetSetup("Hidden", {}))
        # _xml_ column
        lyr.setEditorWidgetSetup(2, QgsEditorWidgetSetup("Hidden", {}))
        lyr.setDisplayExpression("fid")
        
        QgsProject.instance().addMapLayer(lyr)

    @pyqtSlot()
    def on_addMappingBtn_clicked(self):
        lastRow = self.attributeTable.rowCount()
        self.attributeTable.insertRow(lastRow)
        combo = QComboBox(self.attributeTable)
        combo.addItem("String", QVariant.String)
        combo.addItem("Integer", QVariant.Int)
        combo.addItem("Real", QVariant.Double)
        combo.addItem("Date/Time", QVariant.DateTime)
        self.attributeTable.setCellWidget(lastRow, 1, combo)
        self.attributeTable.setItem(lastRow, 0, QTableWidgetItem())
        self.attributeTable.setItem(lastRow, 2, QTableWidgetItem())

    @pyqtSlot()
    def on_removeMappingBtn_clicked(self):
        idx = self.attributeTable.currentIndex()
        self.attributeTable.removeRow(idx.row())

    def onSelectMapping(self, selected, deselected):
        self.removeMappingBtn.setEnabled(selected != -1)

