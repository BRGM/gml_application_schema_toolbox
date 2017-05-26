# -*- coding: utf-8 -*-

import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QFileDialog

from qgis.core import QgsProject, QgsEditFormConfig, QgsEditorWidgetSetup

from ..settings import settings
from ..load_gml_as_xml import load_as_xml_layer

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'import_xml_panel.ui'))


def show_xml_init_code():
    return """
def my_form_open(dialog, layer, feature):
    from gml_application_schema_toolbox import main as mmain
    mmain.add_xml_tree_to_form(dialog, layer, feature)
"""

class ImportXmlPanel(BASE, WIDGET):

    def __init__(self, parent=None):
        super(ImportXmlPanel, self).__init__(parent)
        self.setupUi(self)

    @pyqtSlot()
    def on_gmlPathButton_clicked(self):
        gml_path = settings().value("gml_path", "")
        path, filter = QFileDialog.getOpenFileName(self,
                                                   self.tr("Open GML file"),
                                                   gml_path,
                                                   self.tr("GML files (*.gml *.xml)"))
        if path:
            settings().setValue("gml_path", os.path.dirname(path))
            self.gmlPathLineEdit.setText(path)

    @pyqtSlot()
    def on_importButton_clicked(self):
        gml_path = self.gmlPathLineEdit.text()
        lyr = load_as_xml_layer(gml_path, is_remote = False)
        QgsProject.instance().addMapLayer(lyr)

        conf = lyr.editFormConfig()
        conf.setInitCode(show_xml_init_code())
        conf.setInitFunction("my_form_open")
        conf.setInitCodeSource(QgsEditFormConfig.CodeSourceDialog)
        lyr.setEditFormConfig(conf)
        # id column
        lyr.setEditorWidgetSetup(0, QgsEditorWidgetSetup("Hidden", {}))
        # _xml_ column
        lyr.setEditorWidgetSetup(2, QgsEditorWidgetSetup("Hidden", {}))
        lyr.setDisplayExpression("fid")
        
