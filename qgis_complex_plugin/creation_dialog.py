import os

from PyQt4 import QtGui, uic
from PyQt4.QtCore import *
from PyQt4.QtGui import *

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'creation_dialog.ui'))

class CreationDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(CreationDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.browseButton.clicked.connect(self.onBrowse)
        self.addMappingBtn.clicked.connect(self.onAddMapping)
        self.removeMappingBtn.clicked.connect(self.onRemoveMapping)
        self.attributeTable.selectionModel().selectionChanged.connect(self.onSelectMapping)

    def onBrowse(self):
        openDir = QSettings("complex_features").value("xml_file_location", "")
        xml_file = QFileDialog.getOpenFileName (None, "Select XML File", openDir, "*.xml;;*.gml")
        if xml_file:
            QSettings("complex_features").setValue("xml_file_location", os.path.dirname(xml_file))
            self.filenameText.setText(xml_file)

    def onSelectMapping(self, selected, deselected):
        self.removeMappingBtn.setEnabled(selected != -1)

    def onAddMapping(self):
        self.attributeTable.insertRow(0)
        lastRow = self.attributeTable.rowCount() - 1
        combo = QComboBox(self.attributeTable)
        combo.addItem("Integer", QVariant.Int)
        combo.addItem("Real", QVariant.Double)
        combo.addItem("String", QVariant.String)
        self.attributeTable.setCellWidget(lastRow, 1, combo)

    def onRemoveMapping(self):
        idx = self.attributeTable.currentIndex()
        self.attributeTable.removeRow(idx.row())

    def attribute_mapping(self):
        """Returns the attribute mapping
        { 'attribute1' : '//xpath/expression' }
        """
        mapping = {}
        for i in range(self.attributeTable.rowCount()):
            attr = self.attributeTable.item(i, 0).text()
            xpath = self.attributeTable.item(i, 2).text()
            combo = self.attributeTable.cellWidget(i, 1)
            type = combo.itemData(combo.currentIndex())
            mapping[attr] = (xpath, type)
        return mapping

    def source(self):
        """Returns a pair (isRemote:bool, url:str)"""
        if self.filenameRadio.isChecked():
            return (False, self.filenameText.text())
        #else
        return (True, self.urlText.text())
