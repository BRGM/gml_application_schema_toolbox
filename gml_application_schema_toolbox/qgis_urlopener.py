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
# -*- coding: utf-8 -*-
from PyQt4.QtCore import QUrl, QEventLoop
from PyQt4.QtNetwork import QNetworkRequest, QNetworkAccessManager
from StringIO import StringIO
from qgis.core import QgsNetworkAccessManager

__network_manager = None

def remote_open_from_qgis(uri):
    """Opens a remote URL using QGIS proxy preferences"""
    global __network_manager
    if __network_manager is None:
        __network_manager = QNetworkAccessManager()
        __network_manager.setProxy(QgsNetworkAccessManager.instance().proxy())
    pause = QEventLoop()
    req = QNetworkRequest(QUrl.fromEncoded(uri))
    req.setRawHeader("Accept", "application/xml")
    req.setRawHeader("Accept-Language", "fr")
    reply = __network_manager.get(req)
    reply.finished.connect(pause.quit)
    def onError(self):
        pause.quit()
        raise RuntimeError("Network problem when downloading {}".format(uri))
    reply.error.connect(onError)
    pause.exec_()
    r = str(reply.readAll())
    reply.close()
    return StringIO(r)
