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
from __future__ import absolute_import
from builtins import str
from builtins import range
from builtins import object
# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from ..gml2relational.xml_utils import no_prefix, split_tag

from . import viewers_utils

from datetime import datetime
import time
import os

class PlotView(QGraphicsView):
    def __init__( self, yTitle, parent = None ):
        QGraphicsView.__init__( self, parent )
        self.setScene( PlotScene(yTitle, parent) )
        # enable mousmove when no mouse button is pressed
        self.setMouseTracking( True )
        # set fixed height and scrollbat policies
        self.setVerticalScrollBarPolicy( Qt.ScrollBarAlwaysOff )
        self.setHorizontalScrollBarPolicy( Qt.ScrollBarAlwaysOff )

    def clear( self ):
        self.scene().clear()

    # sceneRect is always set to the resize event size
    # this way, 1 pixel in the scene is 1 pixel on screen
    def resizeEvent( self, event ):
        QGraphicsView.resizeEvent( self, event )
        r = self.scene().sceneRect()
        self.scene().setSceneRect( QRectF( 0, 0, event.size().width(), event.size().height() ) )
        self.displayPlot()

    def setData(self, data):
        self.scene().setData(data)
        
    def displayPlot(self):
        self.scene().displayPlot()

    def mouseMoveEvent( self, event ):
        (x,y) = (event.x(), event.y())
        pt = self.mapToScene( x, y )
        self.scene().onMouseOver( pt )

class PlotScene(QGraphicsScene):

    def __init__( self, yTitle, parent ):
        QGraphicsScene.__init__( self, parent )
        # width of the scale bar
        fm = QFontMetrics(QFont())
        # width = size of "100.0" with the default font + 10%
        self.yTitle = yTitle
        self.barWidth = max(fm.width(yTitle), fm.width("000.00"))
        self.xOffset = self.barWidth
        self.yOffset = fm.height() * 2

        # define the transformation between distance, altitude and scene coordinates
        self.xRatio = 1.0
        self.yRatio = 1.0

        self.marker = PointMarker(self)

        self.clear()

    def clear( self ):
        QGraphicsScene.clear( self )
        self.data = []
        self.xMin = 0
        self.xMax = 0
        self.yMin = 0
        self.yMax = 0

    def setSceneRect( self, rect ):
        QGraphicsScene.setSceneRect( self, rect )
        w = rect.width() - self.barWidth
        if self.xMax != self.xMin:
            self.xRatio = w / (self.xMax - self.xMin)
        else:
            self.xRatio = 1.0
        h = rect.height() - self.yOffset * 2
        if self.yMax != self.yMin:
            self.yRatio = h / (self.yMax-self.yMin)
        else:
            self.yRatio = 1.0

    # convert distance to scene coordinate
    def xToScene( self, x ):
        return (x - self.xMin) * self.xRatio + self.xOffset
    # convert altitude to scene coordinate
    def yToScene( self, y ):
        return self.sceneRect().height() - ((y - self.yMin)* self.yRatio + self.yOffset)

    def setData(self, data):
        self.data = data
        self.xMin = None
        self.xMax = None
        self.yMin = None
        self.yMax = None
        for x, y, _ in self.data:
            if x > self.xMax or self.xMax is None:
                self.xMax = x
            if x < self.xMin or self.xMin is None:
                self.xMin = x
            if y > self.yMax or self.yMax is None:
                self.yMax = y
            if y < self.yMin or self.yMin is None:
                self.yMin = y
        # update ratio and offset
        self.setSceneRect(self.sceneRect())

    def displayPlot( self ):
        QGraphicsScene.clear( self )
        self.marker.clear()
        r = self.sceneRect();

        # display lines fitting in sceneRect
        poly = QPolygonF()
        for x, y, _ in self.data:
            poly.append( QPointF(self.xToScene(x), self.yToScene(y)) )
        # close the polygon
        x2 = self.xToScene(self.xMax)
        y2 = self.sceneRect().height()
        poly.append( QPointF(x2, y2) )
        x2 = self.barWidth
        poly.append( QPointF(x2, y2) )
        x2 = self.xToScene(self.xMin)
        y2 = self.yToScene(0)
        poly.append( QPointF(x2, y2) )
        brush = QBrush(QColor("#DCF1F7"))
        pen = QPen()
        pen.setWidth(0)
        self.addPolygon( poly, pen, brush )

        # horizontal line on ymin and ymax
        self.addLine( self.barWidth-5, self.yToScene(self.yMin), self.barWidth+5, self.yToScene(self.yMin) );
        self.addLine( self.barWidth-5, self.yToScene(self.yMax), self.barWidth+5, self.yToScene(self.yMax) );

        # display scale
        self.addLine( self.barWidth, 0, self.barWidth, self.sceneRect().height() )

        font = QFont()
        fm = QFontMetrics( font )
        t1 = self.addText( "%.1f" % self.yMin )
        t1.setPos( 0, self.yToScene(self.yMin)-fm.ascent())
        t2 = self.addText( "%.1f" % self.yMax )
        t2.setPos( 0, self.yToScene(self.yMax)-fm.ascent())

        # Z(m)
        t3 = self.addText(self.yTitle)
        t3.setPos( 0, 0 )

    # called to add a circle on top of the current altitude profile
    # point : QPointF of the mouse position (in scene coordinates)
    # xRatio, yRatio : factors to convert from view coordinates to scene coordinates
    def onMouseOver( self, point ):
        px = point.x()

        # look for the vertex
        i = -1
        for x, y, xValue in self.data:
            ax = self.xToScene(x)
            if ax > px:
                break
            i += 1
        if i == -1:
            return
        
        self.marker.setText( "x = %s\ny = %.2f" % (xValue, y) )
        self.marker.moveTo( ax, self.yToScene(y) )

# graphics items that are displayed on mouse move on the altitude curve
class PointMarker(object):
    def __init__( self, scene ):
        # circle item
        self.circle = None
        # text item
        self.text = None
        self.textWidth = 0.0
        self.textHeight = 0.0
        self.rect = None
        # the graphics scene
        self.scene = scene

    def clear( self ):
        self.circle = None
        self.text = None

    def setText( self, text ):
        if not self.text:
            font = QFont()
            font.setPointSize(10)
            self.rect = self.scene.addRect(QRectF(0,0,0,0), QPen(), QBrush(QColor("white")))
            self.text = self.scene.addText("", font)
        self.text.setPlainText( text )

        self.textWidth = 0.0
        self.textHeight = 0.0
        for line in text.split('\n'):
            fm = QFontMetrics(self.text.font())
            fw = fm.width(line)
            self.textHeight += fm.height()
            if fw > self.textWidth:
                self.textWidth = fw

    def moveTo( self, x, y ):
        if not self.circle:
            brush = QBrush( QColor( 0, 0, 200 ) ) # blue brush
            self.circle = self.scene.addEllipse( 0,0,4,4,QPen(),brush)

        self.circle.setRect( x-4, y-4, 8, 8 )
        if self.text:
            rw = self.textWidth + 10
            rh = self.textHeight + 10
            if x + self.textWidth > self.scene.width():
                self.rect.setRect(self.scene.width() - self.textWidth, y, rw, rh)
                self.text.setPos(self.scene.width() - self.textWidth, y)
            else:
                self.rect.setRect(x, y, rw, rh)
                self.text.setPos(x, y)

class WML2TimeSeriesViewer(QWidget):
    @classmethod
    def name(cls):
        return "WML2 Time series"
    
    @classmethod
    def table_name(cls):
        # the table name for the relational model
        return "MeasurementTimeseriesType"

    @classmethod
    def xml_tag(cls):
        # the XML tag (with namespace) this widget is meant for
        return "{http://www.opengis.net/waterml/2.0}MeasurementTimeseries"

    @classmethod
    def init_from_xml(cls, xml_tree):
        # parse data
        data = []
        yTitle = 'value'
        title = ''
        for k, v in xml_tree.attrib.items():
            ns, tag = split_tag(k)
            if ns.startswith('http://www.opengis.net/gml') and tag == "id":
                title = v
        for child in xml_tree:
            tag = no_prefix(child.tag)
            if tag == 'point':
                tm = time.mktime(datetime.strptime(child[0][0].text, "%Y-%m-%dT%H:%M:%S.000Z").timetuple())
                value = float(child[0][1].text)
                data.append((tm, value, child[0][0].text))
            elif tag == 'defaultPointMetadata':
                for c in child[0]:
                    if c.tag == '{http://www.opengis.net/waterml/2.0}uom':
                        yTitle = c.attrib['code']
        return cls(title, yTitle, data)

    @classmethod
    def init_from_model(cls, model, sqlite3_conn, id, parent_widget = None):
        title = id
        table = model.tables()[cls.table_name()]
        ytitle = viewers_utils.xpath_on_db(model, table, "defaultPointMetadata/DefaultTVPMeasurementMetadata/uom/@code", id, sqlite3_conn)[0]
        times = viewers_utils.xpath_on_db(model, table, "point/MeasurementTVP/time/text()", id, sqlite3_conn)
        y = viewers_utils.xpath_on_db(model, table, "point/MeasurementTVP/value/text()", id, sqlite3_conn)

        data = []
        for i in range(len(times)):
            tm = time.mktime(datetime.strptime(times[i], "%Y-%m-%dT%H:%M:%S.000Z").timetuple())
            value = float(y[i])
            data.append((tm, value, times[i]))
        return cls(title, ytitle, data, parent_widget)
        
    
    def __init__(self, title, yTitle, data, parent = None):
        QWidget.__init__(self, parent)

        self.setWindowTitle("TimeSeries viewer")

        # sort data by x
        data.sort(key = lambda x: x[0])

        formLayout = QFormLayout()
        # id
        titleW = QLineEdit(title, self)
        titleW.setReadOnly(True)
        formLayout.addRow("ID", titleW)

        # start and end time
        sdt = QDateTime.fromString(data[0][2], "yyyy-MM-ddTHH:mm:ss.zZ")
        edt = QDateTime.fromString(data[-1][2], "yyyy-MM-ddTHH:mm:ss.zZ")
        startTimeW = QDateTimeEdit(sdt)
        startTimeW.setReadOnly(True)
        endTimeW = QDateTimeEdit(edt)
        endTimeW.setReadOnly(True)
        formLayout.addRow("Start time", startTimeW)
        formLayout.addRow("End time", endTimeW)

        # unit of measure
        unitW = QLineEdit(yTitle)
        unitW.setReadOnly(True)
        formLayout.addRow("Unit", unitW)

        # min / max value
        minValue = min([x[1] for x in data])
        maxValue = max([x[1] for x in data])
        minValueW = QLineEdit(str(minValue))
        minValueW.setReadOnly(True)
        maxValueW = QLineEdit(str(maxValue))
        maxValueW.setReadOnly(True)
        formLayout.addRow("Min value", minValueW)
        formLayout.addRow("Max value", maxValueW)

        # the plot
        layout = QVBoxLayout()
        self.plot = PlotView(yTitle, self)
        layout.addLayout(formLayout)
        layout.addWidget(self.plot)
        self.setLayout(layout)

        self.plot.setData(data)
        self.resize(800,600)

    @classmethod
    def icon(cls):
        """Must return a QIcon"""
        return QIcon(os.path.join(os.path.dirname(__file__), "plot.svg"))
