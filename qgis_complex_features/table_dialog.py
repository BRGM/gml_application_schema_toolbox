from PyQt4 import QtGui
from PyQt4.QtGui import QWidget, QListWidget, QVBoxLayout, QSplitter
from identify_dialog import IdentifyDialog

class TableDialog(QtGui.QWidget):
    def __init__(self, layer, parent=None):
        """Constructor.
        :param layer: QgsVectorLayer the feature is from
        """
        super(TableDialog, self).__init__(parent)

        self.setWindowTitle("Feature list")
        self.resize(1000, 700)

        self.featureList = QListWidget()
        self.identifyWidget = IdentifyDialog(layer)
        
        self.mainLayout = QVBoxLayout(self)

        self.splitter = QSplitter(self)
        self.splitter.addWidget(self.featureList)
        self.splitter.addWidget(self.identifyWidget)

        self.mainLayout.addWidget(self.splitter)
        self.setLayout(self.mainLayout)

        # populate the feature list
        self.layer = layer
        self.features = list(layer.getFeatures())

        for f in self.features:
            self.featureList.addItem(f.attribute("id"))

        self.featureList.selectionModel().currentRowChanged.connect(self.onRowChanged)

    def onRowChanged(self, current, previous):
        i = current.row()
        self.identifyWidget.updateFeature(self.features[i])
        self.identifyWidget.show()
        
