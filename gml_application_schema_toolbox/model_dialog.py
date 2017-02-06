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
from builtins import next
from builtins import range
# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

import os
import math

class ModelDialog(QGraphicsView):
    
    tableSelected = pyqtSignal(str)
    
    def __init__(self, model, parent = None):
        QGraphicsView.__init__(self, parent)

        scene = ModelDialogScene(model, parent)
        scene.tableSelected.connect(self.tableSelected)
        self.setScene(scene)
        self.setRenderHints(QPainter.Antialiasing)

    def mouseMoveEvent(self, event):
        self.scene().mouseMoveEvent(self.mapToScene(event.pos()))

def spiral_iterator():
    # current vector
    dx = 1
    dy = 0
    # current segment length
    segment_length = 1

    # position
    x = 0
    y = 0
    yield x, y
    segment_passed = 0
    while True:
        # make a step
        x += dx
        y += dy
        segment_passed += 1
        yield x, y

        if segment_passed == segment_length:
            segment_passed = 0
            # rotation directions
            dx, dy = -dy, dx

            if dy == 0:
                segment_length += 1

class TableWidget(QWidget):
    
    linkActivated = pyqtSignal(str)
    
    def __init__(self, table):
        QWidget.__init__(self)

        layout = QVBoxLayout()

        hlayout = QHBoxLayout()
        l = QLabel(table.name())
        font = l.font()
        font.setBold(True)
        l.setFont(font)
        
        hlayout.addWidget(l)
        open_table_btn = QToolButton()
        icon = QIcon(os.path.dirname(__file__) + "/mActionOpenTableGML.svg")
        open_table_btn.setIcon(icon)
        open_table_btn.resize(32, 32)
        open_table_btn.clicked.connect(lambda checked: self.linkActivated.emit(table.name()))
        hlayout.addWidget(open_table_btn)
        
        f = QFrame()
        f.setFrameStyle(QFrame.Panel | QFrame.Plain)
        f.setLineWidth(2.0)
        f.setLayout(hlayout)

        layout.addWidget(f)

        self.attribute_label = QLabel()
        names = [f.name() for f in table.columns()]
        names += [l.name() + "_id" for l in table.links() if l.max_occurs() == 1]
        names += [l.ref_table().name() + "_id" for l in table.back_links()]

        self.attribute_label.setText("\n".join(names))
        v2 = QVBoxLayout()
        v2.addWidget(self.attribute_label)

        self.attribute_frame = QFrame()
        self.attribute_frame.setFrameStyle(QFrame.Panel | QFrame.Plain)
        self.attribute_frame.setLineWidth(2.0)
        self.attribute_frame.setLayout(v2)
        layout.addWidget(self.attribute_frame)

        self.setLayout(layout)

        fm = QFontMetricsF(self.attribute_label.font())
        self.__font_height = fm.height()
        margins = layout.contentsMargins()

        self.attribute_x_offset = margins.left()
        self.attribute_x2_offset = margins.right()

    def attributeCoords(self, idx):
        # returns the box coordinates of the idx-th attribute
        offset_y = self.attribute_label.y() + self.attribute_frame.y()
        offset_x = self.attribute_x_offset
        x = self.x() + offset_x
        w = self.width() - offset_x - self.attribute_x2_offset
        y = self.y() + offset_y + self.__font_height * idx
        h = self.__font_height
        return (x, y, w, h)

def horizontal_intersection(line, y, xmin, xmax):
    p = QPointF()
    r = line.intersect(QLineF(xmin, y, xmax, y), p)
    if r != 0 and xmin <= p.x() and p.x() <= xmax:
        return p
    return None

def vertical_intersection(line, x, ymin, ymax):
    p = QPointF()
    r = line.intersect(QLineF(x, ymin, x, ymax), p)
    if r != 0 and ymin <= p.y() and p.y() <= ymax:
        return p
    return None

def disable_link_item(item):
    p = item.pen()
    p.setColor(QColor(200, 200, 200))
    item.setPen(p)
    if hasattr(item, "brush"):
        b = item.brush()
        b.setColor(QColor(200, 200, 200))
        item.setBrush(b)
    item.setZValue(-1)
def enable_link_item(item):
    p = item.pen()
    p.setColor(QColor(0, 0, 0))
    item.setPen(p)
    if hasattr(item, "brush"):
        b = item.brush()
        b.setColor(QColor(0, 0, 0))
        item.setBrush(b)
    item.setZValue(1)

class ModelDialogScene(QGraphicsScene):
    
    tableSelected = pyqtSignal(str)
    
    def __init__(self, model, parent):
        QGraphicsScene.__init__(self, parent)

        tables_coords = []
        spiral = spiral_iterator()
        min_grid_x = None
        max_grid_x = None
        min_grid_y = None
        max_grid_y = None
        self.table_items = {}
        for table_name, table in model.tables().items():
            # widget, grid_x, grid_y, x, y
            grid_x, grid_y = next(spiral)
            if grid_x > max_grid_x or max_grid_x is None:
                max_grid_x = grid_x
            if grid_x < min_grid_x or min_grid_x is None:
                min_grid_x = grid_x
            if grid_y > max_grid_y or max_grid_y is None:
                max_grid_y = grid_y
            if grid_y < min_grid_y or min_grid_y is None:
                min_grid_y = grid_y
            w = TableWidget(table)
            w.linkActivated.connect(self.tableSelected)
            tw = self.addWidget(w)
            tables_coords.append((tw, grid_x, grid_y, 0, 0, table_name))
            self.table_items[table_name] = tw

        # resolve columns / rows size
        column_width = {}
        row_height = {}
        for table, grid_x, grid_y, x, y, _ in tables_coords:
            wmax = column_width.get(grid_x)
            hmax = row_height.get(grid_y)
            wsize = table.widget().size()
            if wsize.width() > wmax or wmax is None:
                column_width[grid_x] = wsize.width()
            if wsize.height() > hmax or hmax is None:
                row_height[grid_y] = wsize.height()

        total_width = sum(column_width.values())
        total_height = sum(row_height.values())

        # resolve coordinates
        column_x = {}
        row_y = {}
        w = 0
        for x in range(min_grid_x, max_grid_x+1):
            column_x[x] = w
            w += column_width[x]
        h = 0
        for y in range(min_grid_y, max_grid_y+1):
            row_y[y] = h
            h += row_height[y]

        table_pos = {}
        for i in range(len(tables_coords)):
            table, grid_x, grid_y, _, _, table_name = tables_coords[i]
            wsize = table.widget().size()
            x = column_x[grid_x] + (column_width[grid_x] - wsize.width()) / 2.0
            y = row_y[grid_y] + (row_height[grid_y] - wsize.height()) / 2.0
            tables_coords[i] = (table, x, y)
            table_pos[table_name] = (x, y, wsize.width(), wsize.height(), table)
            table.setPos(x, y)

        def distance(p1, p2):
            l = QLineF(p1, p2)
            return l.length()

        # display links arrows
        def add_link(table_name, table_name2, y_idx):
            tx, ty, tw, th, table = table_pos[table_name]
            tx2, ty2, tw2, th2, _ = table_pos[table_name2]
            (ax, ay, aw, ah) = table.widget().attributeCoords(y_idx)
            l1 = QLineF(ax - 3,      ay + ah / 2.0, tx2 + tw2 / 2.0, ty2 + th2 / 2.0)
            l2 = QLineF(ax + aw + 3, ay + ah / 2.0, tx2 + tw2 / 2.0, ty2 + th2 / 2.0)
            if l1.length() < l2.length():
                p1 = l1.p1()
                l = l1
            else:
                p1 = l2.p1()
                l = l2

            # add a diamond
            ds = 6
            dbrush = QBrush(QColor("black"))
            diamond = QPolygonF([p1 + QPointF(0, ds), p1 + QPointF(ds, 0), p1 + QPointF(0, -ds), p1 + QPointF(-ds, 0), p1 + QPointF(0,ds)])
            i1 = self.addPolygon(diamond, QPen(), dbrush)

            # cross with the second table widget
            points = [horizontal_intersection(l, ty2,       tx2, tx2 + tw2),
                      horizontal_intersection(l, ty2 + th2, tx2, tx2 + tw2),
                      vertical_intersection(l, tx2,       ty2, ty2 + th2),
                      vertical_intersection(l, tx2 + tw2, ty2, ty2 + th2)]
            pp = [p for p in points if p is not None]
            p2 = min(pp, key = lambda p: distance(p1, p))
            l = QLineF(p1, p2)            
            i2 = self.addLine(l)
            i2.setZValue(1)
            alpha = math.atan2( p2.y() - p1.y(), p2.x() - p1.x())
            alpha1 = alpha + 30.0 / 180.0 * math.pi
            alpha2 = alpha - 30.0 / 180.0 * math.pi
            r = -10
            p3 = QPointF(r * math.cos(alpha1), r * math.sin(alpha1)) + p2
            p4 = QPointF(r * math.cos(alpha2), r * math.sin(alpha2)) + p2
            i3 = self.addLine(QLineF(p2, p3))
            i4 = self.addLine(QLineF(p2, p4))
            return [i1, i2, i3, i4]

        for table_name, table in model.tables().items():
            tw = self.table_items[table_name]
            y = len(table.columns())
            items = [tw]
            for l in table.links():
                if l.max_occurs() != 1:
                    continue
                items += add_link(table_name, l.ref_table().name(), y)
                y += 1
            for l in table.back_links():
                items += add_link(table_name, l.ref_table().name(), y)
                y += 1
            self.table_items[table_name] = items

            # make items invisible for now
            for item in items[1:]:
                disable_link_item(item)

        #self.marker = self.addRect(0, 0, 2, 2)

    def mouseMoveEvent(self, pos):
        x = pos.x()
        y = pos.y()
        #self.marker.setPos(x, y)
        for table_name, items in self.table_items.items():
            table_item = items[0]
            if 0 <= x - table_item.x() <= table_item.widget().width() and \
               0 <= y - table_item.y() <= table_item.widget().height():
                show = True
            else:
                show = False
            for item in items[1:]:
                if show:
                    enable_link_item(item)
                else:
                    disable_link_item(item)
