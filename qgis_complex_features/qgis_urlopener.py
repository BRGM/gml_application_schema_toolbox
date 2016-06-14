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
