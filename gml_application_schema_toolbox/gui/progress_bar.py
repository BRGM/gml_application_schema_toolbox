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

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QDialog, QProgressBar, QLabel, QVBoxLayout

class ProgressBarLogger(QDialog):
    """A simple dialog with a progress bar and a label"""
    def __init__(self, title = None):
        QDialog.__init__(self, None)
        if title is not None:
            self.setWindowTitle(title)
        self.__label = QLabel(self)
        self.__layout = QVBoxLayout()
        self.__layout.addWidget(self.__label)
        self.__progress = QProgressBar(self)
        self.__layout.addWidget(self.__progress)
        self.setLayout(self.__layout)
        self.resize(600, 70)
        self.setFixedSize(600, 70)
        self.__progress.hide()
        self.show()

    def set_text(self, t):
        """Gets called when a text is to be logged"""
        if isinstance(t, tuple):
            lvl, msg = t
        else:
            msg = t
        self.__label.setText(msg)
        QCoreApplication.processEvents()

    def set_progress(self, i, n):
        """Gets called when there is a progression"""
        self.__progress.show()
        self.__progress.setMinimum(0)
        self.__progress.setMaximum(n)
        self.__progress.setValue(i)
        QCoreApplication.processEvents()
