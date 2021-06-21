"""
/**
 *   Copyright (C) 2016 BRGM (http:///brgm.fr)
 *   Copyright (C) 2016 Oslandia <infos@oslandia.com>
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


import os
from builtins import range, str

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDir, QSettings, QVariant
from qgis.PyQt.QtGui import Qt
from qgis.PyQt.QtWidgets import QComboBox, QDialog, QFileDialog, QTableWidgetItem

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "creation_dialog.ui")
)


class CreationDialog(QDialog, FORM_CLASS):
    def __init__(
        self,
        xml_uri=None,
        is_remote: bool = False,
        attributes={},
        geometry_mapping=None,
        output_filename=None,
        parent=None,
    ):
        """Constructor."""
        super(CreationDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # populate widgets if passed at the construction
        self.replaceLayerChck.setEnabled(xml_uri is not None)
        if xml_uri is not None:
            if is_remote:
                self.urlText.setText(xml_uri)
                self.urlRadio.setChecked(True)
            else:
                self.filenameText.setText(QDir.fromNativeSeparators(xml_uri))
                self.filenameRadio.setChecked(True)
            self.replaceLayerChck.setCheckState(Qt.Checked)

            for aname, v in attributes.items():
                xpath, attr_type = v
                self.onAddMapping()  # add a row
                last = self.attributeTable.rowCount() - 1
                self.attributeTable.item(last, 0).setText(aname)
                self.attributeTable.cellWidget(last, 1).setCurrentIndex(
                    [
                        QVariant.String,
                        QVariant.Int,
                        QVariant.Double,
                        QVariant.DateTime,
                    ].index(attr_type)
                )
                self.attributeTable.item(last, 2).setText(xpath)

            self.geometryColumnCheck.setChecked(True)
            self.geometryColumnEdit.setText(geometry_mapping)

            self.outFilenameText.setText(QDir.fromNativeSeparators(output_filename))

        else:
            # new dialog
            is_remote = (
                QSettings("complex_features").value("is_remote", "false") == "true"
            )
            source_url = QSettings("complex_features").value("source_url", "")
            if is_remote:
                self.urlRadio.setChecked(True)
                self.urlText.setText(source_url)
            else:
                self.filenameRadio.setChecked(True)
                self.filenameText.setText(QDir.fromNativeSeparators(source_url))

            # output file name
            import tempfile

            f = tempfile.NamedTemporaryFile()
            self.outFilenameText.setText(QDir.fromNativeSeparators(f.name))
            f.close()

            import_type = int(QSettings("complex_features").value("import_type", "0"))
            self.mImportTypeCombo.setCurrentIndex(import_type)
            self.mStackedWidgets.setCurrentIndex(import_type)

        self.browseButton.clicked.connect(self.onBrowse)
        self.addMappingBtn.clicked.connect(self.onAddMapping)
        self.removeMappingBtn.clicked.connect(self.onRemoveMapping)
        self.attributeTable.selectionModel().selectionChanged.connect(
            self.onSelectMapping
        )
        self.browseOutButton.clicked.connect(self.onBrowseOut)

    def onBrowse(self):
        openDir = QSettings("complex_features").value("xml_file_location", "")
        xml_file, __ = QFileDialog.getOpenFileName(
            None, "Select XML File", openDir, "*.xml;;*.gml"
        )
        if xml_file:
            QSettings("complex_features").setValue(
                "xml_file_location", os.path.dirname(xml_file)
            )
            self.filenameText.setText(xml_file)

    def onBrowseOut(self):
        openDir = QSettings("complex_features").value("out_file_location", "")
        sqlite_file, __ = QFileDialog.getSaveFileName(
            None, "Select Sqlite File", openDir, "*.sqlite"
        )
        if sqlite_file:
            QSettings("complex_features").setValue(
                "out_file_location", os.path.dirname(sqlite_file)
            )
            self.outFilenameText.setText(sqlite_file)

    def onSelectMapping(self, selected, deselected):
        self.removeMappingBtn.setEnabled(selected != -1)

    def onAddMapping(self):
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

    def onRemoveMapping(self):
        idx = self.attributeTable.currentIndex()
        self.attributeTable.removeRow(idx.row())

    def accept(self):
        is_remote, src = self.source()
        # fix print with import
        QSettings("complex_features").setValue(
            "is_remote", "true" if is_remote else "false"
        )
        QSettings("complex_features").setValue("source_url", src)
        QSettings("complex_features").setValue(
            "import_type", str(self.mImportTypeCombo.currentIndex())
        )

        QDialog.accept(self)

    def import_type(self):
        return self.mImportTypeCombo.currentIndex()

    def attribute_mapping(self):
        """Returns the attribute mapping
        { 'attribute1' : '//xpath/expression' }
        """
        mapping = {}
        for i in range(self.attributeTable.rowCount()):
            attr = self.attributeTable.item(i, 0).text()
            xpath = self.attributeTable.item(i, 2).text()
            combo = self.attributeTable.cellWidget(i, 1)
            attr_type = combo.itemData(combo.currentIndex())
            mapping[attr] = (xpath, attr_type)
        return mapping

    def geometry_mapping(self):
        """Returns the geometry column XPath or None"""
        if self.geometryColumnCheck.isChecked() and self.geometryColumnEdit.text():
            return self.geometryColumnEdit.text()
        return None

    def source(self):
        """Returns a pair (isRemote:bool, url:str)"""
        if self.filenameRadio.isChecked():
            return (False, QDir.toNativeSeparators(self.filenameText.text()))
        # else
        return (True, self.urlText.text())

    def replace_current_layer(self):
        return self.replaceLayerChck.isChecked()

    def output_filename(self):
        return QDir.toNativeSeparators(self.outFilenameText.text())

    def archive_directory(self):
        return QDir.toNativeSeparators(self.mArchiveDirEdit.text())

    def merge_depth(self):
        return self.mMergeDepthSpin.value()

    def merge_sequences(self):
        return self.mergeSequencesChk.isChecked()

    def enforce_not_null(self):
        return self.mEnforceNotNullChk.isChecked()
