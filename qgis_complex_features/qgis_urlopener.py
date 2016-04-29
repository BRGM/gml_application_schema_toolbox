from PyQt4.QtCore import QUrl, QEventLoop
from PyQt4.QtNetwork import QNetworkRequest
from StringIO import StringIO
from qgis.core import QgsNetworkAccessManager

def remote_open_from_qgis(uri):
    """Opens a remote URL using QGIS proxy preferences"""
    nm = QgsNetworkAccessManager.instance()
    pause = QEventLoop()
    req = QNetworkRequest(QUrl.fromEncoded(uri))
    req.setRawHeader("Accept", "application/xml")
    req.setRawHeader("Accept-Language", "fr")
    reply = nm.get(req)
    reply.finished.connect(pause.quit)
    def onError(self):
        pause.quit()
        raise RuntimeError("Network problem when downloading {}".format(uri))
    reply.error.connect(onError)
    pause.exec_()
    r = str(reply.readAll())
    reply.close()
    return StringIO(r)
