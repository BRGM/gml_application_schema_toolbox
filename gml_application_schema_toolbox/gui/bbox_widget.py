# -*- coding: utf-8 -*-

"""
Inspired by processing.gui.ExtentSelectionPanel

Note that this depends on some processing plugin classes
"""

import os

from qgis.core import QgsRasterLayer, QgsVectorLayer, QgsRectangle
from qgis.gui import QgsMessageBar
from qgis.utils import iface

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QMenu, QAction, QInputDialog
from qgis.PyQt.QtGui import QCursor

from processing.gui.RectangleMapTool import RectangleMapTool
from processing.core.ProcessingConfig import ProcessingConfig
from processing.tools import dataobjects

WIDGET, BASE = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'bbox_widget.ui'))


class BboxWidget(BASE, WIDGET):

    def __init__(self, parent=None):
        super(BboxWidget, self).__init__(parent)
        self.setupUi(self)

        self.btnSelect.clicked.connect(self.selectExtent)

        canvas = iface.mapCanvas()
        self.prevMapTool = canvas.mapTool()
        self.tool = RectangleMapTool(canvas)
        self.tool.rectangleCreated.connect(self.updateExtent)

    def selectExtent(self):
        popupmenu = QMenu()
        useLayerExtentAction = QAction(
            self.tr('Use layer/canvas extent'), self.btnSelect)
        selectOnCanvasAction = QAction(
            self.tr('Select extent on canvas'), self.btnSelect)

        popupmenu.addAction(useLayerExtentAction)
        popupmenu.addAction(selectOnCanvasAction)

        selectOnCanvasAction.triggered.connect(self.selectOnCanvas)
        useLayerExtentAction.triggered.connect(self.useLayerExtent)

        popupmenu.exec_(QCursor.pos())

    def useLayerExtent(self):
        CANVAS_KEY = 'Use canvas extent'
        extentsDict = {}
        extentsDict[CANVAS_KEY] = {"extent": iface.mapCanvas().extent(),
                                   "authid": iface.mapCanvas().mapSettings().destinationCrs().authid()}
        extents = [CANVAS_KEY]
        layers = dataobjects.getAllLayers()
        for layer in layers:
            authid = layer.crs().authid()
            if ProcessingConfig.getSetting(ProcessingConfig.SHOW_CRS_DEF) \
                    and authid is not None:
                layerName = u'{} [{}]'.format(layer.name(), authid)
            else:
                layerName = layer.name()
            extents.append(layerName)
            extentsDict[layerName] = {"extent": layer.extent(), "authid": authid}
        (item, ok) = QInputDialog.getItem(self, self.tr('Select extent'),
                                          self.tr('Use extent from'), extents, False)
        if ok:
            self.setValue(extentsDict[item]["extent"])
            if extentsDict[item]["authid"] != iface.mapCanvas().mapSettings().destinationCrs().authid():
                iface.messageBar().pushMessage(self.tr("Warning"),
                                               self.tr("The projection of the chosen layer is not the same as canvas projection! The selected extent might not be what was intended."),
                                               QgsMessageBar.WARNING, 8)

    def selectOnCanvas(self):
        canvas = iface.mapCanvas()
        canvas.setMapTool(self.tool)
        '''
        self.dialog.showMinimized()
        '''

    def updateExtent(self):
        self.setValue(self.tool.rectangle())

        self.tool.reset()
        canvas = iface.mapCanvas()
        canvas.setMapTool(self.prevMapTool)
        '''
        self.dialog.showNormal()
        self.dialog.raise_()
        self.dialog.activateWindow()
        '''

    def setValue(self, value):
        if isinstance(value, QgsRectangle):
            s = '{},{},{},{}'.format(value.xMinimum(),
                                         value.xMaximum(),
                                         value.yMinimum(),
                                         value.yMaximum())
        elif isinstance(value, str):
            s = value
        else:
            s = ",".join([str(v) for v in value])

        self.leText.setText(s)
        return True

    def value(self):
        return self.leText.text()
