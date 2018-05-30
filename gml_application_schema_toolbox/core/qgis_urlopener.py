# -*- coding: utf-8 -*-

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

from builtins import str

from qgis.PyQt.QtCore import QUrl, QEventLoop
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkAccessManager
from io import BytesIO
from qgis.core import QgsNetworkAccessManager

__network_manager = None

def _sync_get(url):
    global __network_manager
    if __network_manager is None:
        __network_manager = QNetworkAccessManager()
        __network_manager.setProxy(QgsNetworkAccessManager.instance().proxy())
    pause = QEventLoop()
    req = QNetworkRequest(url)
    req.setRawHeader(b"Accept", b"application/xml")
    req.setRawHeader(b"Accept-Language", b"fr")
    reply = __network_manager.get(req)
    reply.finished.connect(pause.quit)
    is_ok = [True]
    def onError(self):
        is_ok[0] = False
        pause.quit()
    reply.error.connect(onError)
    pause.exec_()
    return reply, is_ok[0]

def remote_open_from_qgis(uri):
    """Opens a remote URL using QGIS proxy preferences"""
    reply, is_ok = _sync_get(QUrl.fromEncoded(bytes(uri, "utf8")))
    if not is_ok:
        raise RuntimeError("Network problem when downloading {}".format(uri))
    redirect = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
    # Handle HTTP 302 redirections
    while redirect is not None and not redirect.isEmpty():
        reply, is_ok = _sync_get(redirect)
        if not is_ok:
            raise RuntimeError("Network problem when downloading {}".format(uri))
        redirect = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
    r = bytes(reply.readAll())
    reply.close()
    return BytesIO(r)
