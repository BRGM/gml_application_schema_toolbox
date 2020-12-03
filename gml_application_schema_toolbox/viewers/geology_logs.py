#   Copyright (C) 2016 BRGM (http:///brgm.fr)
#   Copyright (C) 2016 Oslandia <infos@oslandia.com>
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

from __future__ import absolute_import

import os

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from ..core.gmlas_xpath import GmlAsXPathResolver
from ..core.xml_utils import no_prefix, resolve_xpath, split_tag
from . import viewers_utils


class GeologyLogViewer(QWidget):
    @classmethod
    def name(cls):
        return "GW Geology log"

    @classmethod
    def xml_tag(cls):
        # the XML tag (with namespace) this widget is meant for
        return "{http://www.opengis.net/gwml-well/2.2}GW_GeologyLogCoverage"

    @classmethod
    def init_from_xml(cls, xml_tree):
        # parse data
        data = []
        # description = resolve_xpath(xml_tree, "element/value/description/text()")
        ns_map = {
            "swe": "http://www.opengis.net/swe/2.0",
            "ns": "http://www.opengis.net/gwml-well/2.2",
        }
        logs = resolve_xpath(xml_tree, "ns:element/ns:LogValue", ns_map)
        data = []
        for log in logs:
            fromDepth = float(
                resolve_xpath(log, "ns:fromDepth/swe:Quantity/swe:value/text()", ns_map)
            )
            toDepth = float(
                resolve_xpath(log, "ns:toDepth/swe:Quantity/swe:value/text()", ns_map)
            )
            value_text = resolve_xpath(
                log,
                "ns:value/swe:DataRecord/swe:field/swe:Text/swe:value/text()",
                ns_map,
            )
            value_cat = resolve_xpath(
                log,
                "ns:value/swe:DataRecord/swe:field/swe:Category/swe:value/text()",
                ns_map,
            )
            value = value_text if value_text else value_cat
            data.append((fromDepth, toDepth, value))
        return cls("GeologyLogCoverage", data)

    @classmethod
    def init_from_db(
        cls, db_uri, provider, schema, layer_name, pkid_name, pkid_value, parent
    ):
        resolver = GmlAsXPathResolver(db_uri, provider, schema)

        froms = resolver.resolve_xpath(
            layer_name,
            pkid_name,
            pkid_value,
            "element/LogValue/fromDepth/Quantity/value",
        )
        tos = resolver.resolve_xpath(
            layer_name, pkid_name, pkid_value, "element/LogValue/toDepth/Quantity/value"
        )
        cats = resolver.resolve_xpath(
            layer_name,
            pkid_name,
            pkid_value,
            "element/LogValue/value/DataRecord/field/Category/value",
        )
        data = [(float(f), float(t), cat) for (f, t, cat) in zip(froms, tos, cats)]
        return cls("GeologyLogCoverage", data, parent)

    def __init__(self, title, data, parent=None):
        QWidget.__init__(self, parent)

        self.setWindowTitle("Geology log viewer")

        formLayout = QFormLayout()
        # id
        titleW = QLineEdit(title, self)
        titleW.setReadOnly(True)

        formLayout.addRow("Description", titleW)

        # the plot
        layout = QVBoxLayout()
        self.plot = PlotView(self)
        layout.addLayout(formLayout)
        layout.addWidget(self.plot)
        self.setLayout(layout)

        self.plot.setData(data)
        self.resize(800, 600)

    @classmethod
    def icon(cls):
        """Must return a QIcon"""
        return QIcon(os.path.join(os.path.dirname(__file__), "drill.svg"))


class PlotView(QGraphicsView):
    def __init__(self, parent=None):
        QGraphicsView.__init__(self, parent)
        self.setScene(PlotScene(parent))
        # set fixed height and scrollbat policies
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def clear(self):
        self.scene().clear()

    # sceneRect is always set to the resize event size
    # this way, 1 pixel in the scene is 1 pixel on screen
    def resizeEvent(self, event):
        QGraphicsView.resizeEvent(self, event)
        self.scene().setSceneRect(
            QRectF(0, 0, event.size().width(), event.size().height())
        )
        self.displayPlot()

    def setData(self, data):
        self.scene().setData(data)

    def displayPlot(self):
        self.scene().displayPlot()


class PlotScene(QGraphicsScene):
    def __init__(self, parent):
        QGraphicsScene.__init__(self, parent)

        self.zScale = 100.0
        # width (in pixels) of the bar
        self.barWidth = 20
        # offset from the left border
        self.xOffset = 10

        self.clear()

    def clear(self):
        QGraphicsScene.clear(self)
        self.data = []
        self.zMin = 0
        self.zMax = 0
        self.width = 0
        self.zScale = 100.0
        self.legendWidth = 0
        self.xOffset = 5
        self.yOffset = 20

    def setData(self, data):
        fm = QFontMetrics(QFont())
        self.data = data
        self.zMin = None
        self.zMax = None
        self.width = None
        for z1, z2, text in self.data:
            if self.zMin is None or z1 < self.zMin:
                self.zMin = z1
            if self.zMax is None or z2 > self.zMax:
                self.zMax = z2
            tw = fm.width(text)
            if self.width is None or tw > self.width:
                self.width = tw
            tw1 = fm.width("{}".format(z1))
            tw2 = fm.width("{}".format(z2))
            tw = max(tw1, tw2)
            if tw > self.legendWidth:
                self.legendWidth = tw
        # update ratio and offset
        self.setSceneRect(self.sceneRect())

    def setSceneRect(self, rect):
        QGraphicsScene.setSceneRect(self, rect)
        h = rect.height() - self.yOffset * 2
        if self.zMax != self.zMin:
            self.zScale = h / (self.zMax - self.zMin)
        else:
            self.zScale = 1.0

    def displayPlot(self):
        QGraphicsScene.clear(self)
        r = self.sceneRect()
        fm = QFontMetrics(QFont())

        # display lines fitting in sceneRect
        last = None
        for z1, z2, text in self.data:
            brush = QBrush(
                QColor.fromHsl(z2 / (self.zMax - self.zMin) * 360.0, 128, 128)
            )
            self.addRect(
                self.xOffset + self.legendWidth,
                z1 * self.zScale + self.yOffset,
                self.barWidth,
                (z2 - z1) * self.zScale,
                QPen(),
                brush,
            )

            if last is None:
                legend_item = self.addSimpleText("{}".format(z1))
                legend_item.setPos(self.xOffset, z1 * self.zScale + self.yOffset)
            legend_item = self.addSimpleText("{}".format(z2))
            legend_item.setPos(self.xOffset, z2 * self.zScale + self.yOffset)
            last = z2

            text_item = self.addSimpleText(text)
            text_item.setPos(
                self.xOffset * 2 + self.legendWidth + self.barWidth,
                (z1 + z2) / 2.0 * self.zScale - fm.height() / 2.0 + self.yOffset,
            )
