"""
Inspired by processing.gui.ExtentSelectionPanel

Note that this depends on some processing plugin classes
"""

import os

from processing.gui.RectangleMapTool import RectangleMapTool
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRectangle,
)
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QCursor
from qgis.PyQt.QtWidgets import QAction, QInputDialog, QMenu
from qgis.utils import iface

WIDGET, BASE = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "..", "ui", "bbox_widget.ui")
)


class BboxWidget(BASE, WIDGET):
    def __init__(self, parent=None):
        super(BboxWidget, self).__init__(parent)
        self.setupUi(self)

        self.dialog = None

        self.btnSelect.clicked.connect(self.selectExtent)

        canvas = iface.mapCanvas()
        self.prevMapTool = canvas.mapTool()
        self.tool = RectangleMapTool(canvas)
        self.tool.rectangleCreated.connect(self.updateExtent)

    def setDialog(self):
        self._dialog = Dialog

    def selectExtent(self):
        popupmenu = QMenu()
        useLayerExtentAction = QAction(
            self.tr("Use layer/canvas extent"), self.btnSelect
        )
        selectOnCanvasAction = QAction(
            self.tr("Select extent on canvas"), self.btnSelect
        )

        popupmenu.addAction(useLayerExtentAction)
        popupmenu.addAction(selectOnCanvasAction)

        selectOnCanvasAction.triggered.connect(self.selectOnCanvas)
        useLayerExtentAction.triggered.connect(self.useLayerExtent)

        popupmenu.exec_(QCursor.pos())

    def useLayerExtent(self):
        CANVAS_KEY = "Use canvas extent"
        extentsDict = {}
        extentsDict[CANVAS_KEY] = {
            "extent": iface.mapCanvas().extent(),
            "authid": iface.mapCanvas().mapSettings().destinationCrs().authid(),
        }
        extents = [CANVAS_KEY]
        for layer in QgsProject.instance().mapLayers().values():
            authid = layer.crs().authid()
            layerName = layer.name()
            extents.append(layerName)
            extentsDict[layerName] = {"extent": layer.extent(), "authid": authid}
        (item, ok) = QInputDialog.getItem(
            self, self.tr("Select extent"), self.tr("Use extent from"), extents, False
        )
        if ok:
            self.setValue(extentsDict[item]["extent"], extentsDict[item]["authid"])

    def selectOnCanvas(self):
        canvas = iface.mapCanvas()
        canvas.setMapTool(self.tool)
        if self.dialog:
            self.dialog.showMinimized()

    def updateExtent(self):
        self.setValue(
            self.tool.rectangle(),
            iface.mapCanvas().mapSettings().destinationCrs().authid(),
        )

        self.tool.reset()
        canvas = iface.mapCanvas()
        canvas.setMapTool(self.prevMapTool)
        if self.dialog:
            self.dialog.showNormal()
            self.dialog.raise_()
            self.dialog.activateWindow()

    def setValue(self, value, crs_authid):
        if isinstance(value, QgsRectangle):
            s = "{},{},{},{}".format(
                value.xMinimum(), value.yMinimum(), value.xMaximum(), value.yMaximum()
            )
        elif isinstance(value, str):
            s = value
        else:
            s = ",".join([str(v) for v in value])

        s = "{},{}".format(s, crs_authid)

        self.leText.setText(s)
        return True

    def value(self):
        return self.leText.text()

    def rectangle(self):
        if self.value() == "":
            return None
        xmin, ymin, xmax, ymax = [float(x) for x in self.value().split(",")[0:4]]
        return QgsRectangle(xmin, ymin, xmax, ymax)

    def crs(self):
        if self.value() == "":
            return None
        return QgsCoordinateReferenceSystem(self.value().split(",")[4])

    def isValid(self):
        try:
            # rect = self.rectangle()
            crs = self.crs()
            assert crs.isValid()
            return True
        except Exception:
            return False
