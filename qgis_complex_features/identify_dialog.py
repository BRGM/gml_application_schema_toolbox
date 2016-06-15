from PyQt4 import QtGui
from PyQt4.QtCore import QVariant, QDateTime
from PyQt4.QtGui import QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDateTimeEdit
from xml_tree_widget import XMLTreeWidget

class IdentifyDialog(QtGui.QWidget):
    def __init__(self, layer, feature = None, parent=None):
        """Constructor.
        :param layer: QgsVectorLayer the feature is from
        """
        super(IdentifyDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        #self.setupUi(self)

        self.treeWidget = XMLTreeWidget(self)

        self.mainLayout = QVBoxLayout(self)
        self.formLayout = QFormLayout(self)
        self.mainLayout.addLayout(self.formLayout)
        self.mainLayout.addWidget(self.treeWidget)
        self.setLayout(self.mainLayout)
        self.setWindowTitle("Feature Identification")
        self.resize(996, 652)

        self.layer = layer

        for i in range(layer.pendingFields().count()):
            field = layer.pendingFields().at(i)
            if field.name() == "_xml_":
                continue
            if field.typeName() == "qdatetime":
                widget = QDateTimeEdit()
            else:
                widget = QLineEdit()
            widget.setReadOnly(True)
            self.formLayout.addRow(field.name(), widget)

        if feature is not None:
            self.updateFeature(feature)

    def updateFeature(self, feature):
        self.treeWidget.updateFeature(feature)

        for i in range(self.formLayout.rowCount()):
            field_name = self.formLayout.itemAt(i, QFormLayout.LabelRole).widget().text()
            v = feature.attribute(field_name)
            widget = self.formLayout.itemAt(i, QFormLayout.FieldRole).widget()
            if self.layer.pendingFields().field(field_name).typeName() == "qdatetime":
                dt = QDateTime.fromString(v, "yyyy-MM-ddTHH:mm:ss.zZ")
                widget.setDateTime(dt)
            else:
                widget.setText(unicode(v) or "")
        
        
