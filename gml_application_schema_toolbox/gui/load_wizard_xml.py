#! python3  # noqa: E265

# ############################################################################
# ########## Imports ###############
# ##################################

# Standard library
import os

from PyQt5 import uic
from qgis.core import QgsEditorWidgetSetup, QgsProject
from qgis.PyQt.QtCore import QRegExp, QVariant, pyqtSlot
from qgis.PyQt.QtGui import QRegExpValidator
from qgis.PyQt.QtWidgets import QComboBox, QLineEdit, QTableWidgetItem, QWizardPage

from gml_application_schema_toolbox.toolbelt.log_handler import PlgLogger

from ..core.load_gml_as_xml import load_as_xml_layer
from ..gui import qgis_form_custom_widget
from ..gui.progress_bar import ProgressBarLogger

# ############################################################################
# ########## Globals ###############
# ##################################

PAGE_3_W, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "..", "ui", "load_wizard_xml_options.ui")
)

# ############################################################################
# ########## Classes ###############
# ##################################
class LoadWizardXML(QWizardPage, PAGE_3_W):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = PlgLogger().log
        self.setupUi(self)
        self.setFinalPage(True)

        self.attributeTable.selectionModel().selectionChanged.connect(
            self.onSelectMapping
        )
        self.geometryColumnCheck.stateChanged.connect(
            self.geometryColumnEdit.setEnabled
        )
        if __debug__:
            self.log(message=f"DEBUG {__name__} loaded.", log_level=5)

    def nextId(self):
        return -1

    def validatePage(self):
        gml_path = self.wizard().gml_path()

        # get attribute mapping
        mapping = {}
        for i in range(self.attributeTable.rowCount()):
            attr = self.attributeTable.cellWidget(i, 0).text()
            xpath = self.attributeTable.item(i, 2).text()
            combo = self.attributeTable.cellWidget(i, 1)
            attr_type = combo.itemData(combo.currentIndex())
            mapping[attr] = (xpath, attr_type)

        # get geometry mapping
        gmapping = None
        if self.geometryColumnCheck.isChecked() and self.geometryColumnEdit.text():
            gmapping = self.geometryColumnEdit.text()

        # add a progress bar during import
        lyrs = load_as_xml_layer(
            gml_path,
            is_remote=gml_path.startswith("http://") or gml_path.startswith("https://"),
            attributes=mapping,
            geometry_mapping=gmapping,
            logger=ProgressBarLogger("Importing features ..."),
            swap_xy=self.swapXYCheck.isChecked(),
        )

        for lyr in lyrs.values():
            # install an XML tree widget
            qgis_form_custom_widget.install_xml_tree_on_feature_form(lyr)

            # id column
            lyr.setEditorWidgetSetup(0, QgsEditorWidgetSetup("Hidden", {}))
            # _xml_ column
            lyr.setEditorWidgetSetup(2, QgsEditorWidgetSetup("XML", {}))
            lyr.setDisplayExpression("fid")

        QgsProject.instance().addMapLayers(lyrs.values())

        return True

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

        lineEdit = QLineEdit(self.attributeTable)
        # exclude id, fid and _xml from allowed field names
        lineEdit.setValidator(QRegExpValidator(QRegExp("(?!(id|fid|_xml_)).*")))
        self.attributeTable.setCellWidget(lastRow, 0, lineEdit)

        self.attributeTable.setItem(lastRow, 2, QTableWidgetItem())

    @pyqtSlot()
    def on_removeMappingBtn_clicked(self):
        idx = self.attributeTable.currentIndex()
        self.attributeTable.removeRow(idx.row())

    def onSelectMapping(self, selected, deselected):
        self.removeMappingBtn.setEnabled(selected != -1)
