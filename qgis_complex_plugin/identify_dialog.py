from PyQt4 import QtGui
from PyQt4.QtGui import QDialog, QVBoxLayout, QFormLayout, QLineEdit
from xml_tree_widget import XMLTreeWidget

class IdentifyDialog(QtGui.QDialog):
    def __init__(self, layer, feature, parent=None):
        """Constructor.
        :param layer: QgsVectorLayer the feature is from
        :param feature: a QgsFeature
        """
        super(IdentifyDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        #self.setupUi(self)

        self.treeWidget = XMLTreeWidget(layer, feature, self)

        self.mainLayout = QVBoxLayout(self)
        self.formLayout = QFormLayout(self)
        self.mainLayout.addLayout(self.formLayout)
        self.mainLayout.addWidget(self.treeWidget)
        self.setLayout(self.mainLayout)
        self.setWindowTitle("Feature Identification")
        self.resize(996, 652)

        for i in range(layer.pendingFields().count()):
            field = layer.pendingFields().at(i)
            if field.name() == "_xml_":
                continue
            lineEdit = QLineEdit(unicode(feature.attribute(field.name()) or ""))
            lineEdit.setReadOnly(True)
            self.formLayout.addRow(field.name(), lineEdit)
        
        
