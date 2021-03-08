#! python3  # noqa: E265
"""
    An httplib2 replacement that uses `QgsNetworkAccessManager <https://github.com/boundlessgeo/lib-qgis-commons/blob/master/qgiscommons2/network/networkaccessmanager.py>`_

    - Date                 : August 2016
    - Copyright            : (C) 2016 Boundless, http://boundlessgeo.com
    - Email                : apasotti at boundlessgeo dot com
    - Notes                : Enhanced in 2021 by Julien M. for Oslandia

    This program is free software; you can redistribute it and/or modify \
    it under the terms of the GNU General Public License as published by \
    the Free Software Foundation; either version 2 of the License, or \
    (at your option) any later version.
"""

# ############################################################################
# ########## Imports ###############
# ##################################

# Standard library
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Tuple

# PyQGIS
from qgis.core import QgsAuthManager, QgsNetworkAccessManager
from qgis.PyQt.QtCore import QEventLoop, QObject, QUrl, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

# project
from gml_application_schema_toolbox.toolbelt.log_handler import PlgLogger

# ############################################################################
# ########## Globals ###############
# ##################################

DEFAULT_MAX_REDIRECTS: int = 4
logger = logging.getLogger(__name__)
plg_logger = PlgLogger()

# ############################################################################
# ########## Exceptions ############
# ##################################


class RequestsException(Exception):
    pass


class RequestsExceptionTimeout(RequestsException):
    pass


class RequestsExceptionConnectionError(RequestsException):
    pass


class RequestsExceptionUserAbort(RequestsException):
    pass


# ############################################################################
# ########## Classes ###############
# ##################################


class Map(dict):
    """
    Example:
    m = Map({'first_name': 'Eduardo'}, last_name='Pool', age=24, sports=['Soccer'])
    """

    def __init__(self, *args, **kwargs):
        super(Map, self).__init__(*args, **kwargs)
        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    self[k] = v

        if kwargs:
            for k, v in kwargs.items():
                self[k] = v

    def __getattr__(self, attr):
        return self.get(attr)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        super(Map, self).__setitem__(key, value)
        self.__dict__.update({key: value})

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        super(Map, self).__delitem__(key)
        del self.__dict__[key]


class Response(Map):
    pass


class NetworkAccessManager(QObject):
    """This class mimicks httplib2 by using QgsNetworkAccessManager for all
    network calls.

    :param authid: uthentication config id to use during the request, defaults to None
    :type authid: str, optional
    :param disable_ssl_certificate_validation: ignore SSL checks, defaults to False
    :type disable_ssl_certificate_validation: bool, optional
    :param exception_class: Custom exception class, defaults to None
    :type exception_class: object, optional
    :param debug: verbose logging if True, defaults to False
    :type debug: bool, optional



    :Note: If blocking mode returns immediatly it's up to the caller to manage listeners in \
    case of non blocking mode.

    :Example:

    .. code-block:: python

        # Blocking mode
        nam = NetworkAccessManager(authcgf)
        try:
            (response, content) = nam.request('http://www.example.com')
        except RequestsException as e:
            # Handle exception
            pass

        # Non blocking mode
        nam = NetworkAccessManager(authcgf)
        try:
            nam.request('http://www.example.com', blocking=False)
            nam.reply.finished.connect(a_signal_listener)
        except RequestsException as e:
            # Handle exception
            pass

        # Get response using method:
        # nam.httpResult() that return a dictionary with keys:
        #     'status' - http code result come from reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        #     'status_code' - http code result come from reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        #     'status_message' - reply message string from reply.attribute(QNetworkRequest.HttpReasonPhraseAttribute)
        #     'content' - bytearray returned from reply
        #     'ok' - request success [True, False]
        #     'headers' - Dictionary containing the reply header
        #     'reason' - fomatted message string with reply.errorString()
        #     'exception' - the exception returne dduring execution
    """

    finished = pyqtSignal(Response)

    def __init__(
        self,
        authid: str = None,
        disable_ssl_certificate_validation: bool = False,
        exception_class: object = None,
        debug: bool = False,
    ):
        """Initialization."""

        QObject.__init__(self)
        self.disable_ssl_certificate_validation = disable_ssl_certificate_validation
        self.authid = authid
        self.reply = None
        self.debug = debug
        self.exception_class = exception_class
        self.on_abort = False
        self.blocking_mode = False
        self.http_call_result = Response(
            {
                "status": 0,
                "status_code": 0,
                "status_message": "",
                "content": "",
                "ok": False,
                "headers": {},
                "reason": "",
                "exception": None,
                "url": "",
            }
        )

    def httpResult(self):
        return self.http_call_result

    def request(
        self,
        url: str,
        method: str = "GET",
        body=None,
        headers: dict = None,
        redirections: int = DEFAULT_MAX_REDIRECTS,
        connection_type=None,
        blocking: bool = True,
    ) -> Tuple[Response, bytearray]:
        """Make a network request by calling QgsNetworkAccessManager. \
        Redirections argument is ignored and is here only for httplib2 compatibility.

        :param url: URL to request.
        :type url: str
        :param method: HTTP verb as request type, defaults to "GET"
        :type method: str, optional
        :param body: [description], defaults to None
        :type body: [type], optional
        :param headers: HTTP header key:value, defaults to None
        :type headers: dict, optional
        :param redirections: [description], defaults to DEFAULT_MAX_REDIRECTS
        :type redirections: [type], optional
        :param connection_type: [description], defaults to None
        :type connection_type: [type], optional
        :param blocking: sync (True) or async (False) , defaults to True
        :type blocking: bool, optional

        :raises e: [description]
        :raises self.http_call_result.exception: [description]
        :raises self.exception_class: [description]
        :raises RequestsException: [description]

        :return: a tuple of (response, content), the first being and instance of the \
        Response class, the second being a bytearray that contains the response entity body.
        :rtype: Tuple[Response, bytearray]
        """
        # store headers in case of redirections
        self.headers = headers
        self.http_call_result.url = url
        if self.debug:
            plg_logger.log(
                message="DEBUG - http_call request: {0}".format(url), log_level=4
            )

        self.blocking_mode = blocking
        req = QNetworkRequest()

        # -- URL construction
        url = urllib.parse.unquote(url)  # Avoid double quoting form QUrl
        req.setUrl(QUrl(url))

        # -- HEADERS
        if headers is not None:
            # This fixes a weird error with compressed content not being correctly
            # inflated.
            # If you set the header on the QNetworkRequest you are basically telling
            # QNetworkAccessManager "I know what I'm doing, please don't do any content
            # encoding processing".
            # See: https://bugs.webkit.org/show_bug.cgi?id=63696#c1
            try:
                del headers["Accept-Encoding"]
            except KeyError:
                pass
            for k, v in list(headers.items()):
                if self.debug:
                    plg_logger.log(
                        "DEBUG - Setting header %s to %s" % (k, v), log_level=4
                    )
                req.setRawHeader(k, v)

        # -- Authentication configuration
        if self.authid:
            if self.debug:
                plg_logger.log(
                    "DEBUG - Update request w/ authid: {0}".format(self.authid)
                )
            QgsAuthManager.instance().updateNetworkRequest(req, self.authid)

        # -- Perform request
        if self.reply is not None and self.reply.isRunning():
            self.reply.close()
        if method.lower() == "delete":
            func = getattr(QgsNetworkAccessManager.instance(), "deleteResource")
        else:
            func = getattr(QgsNetworkAccessManager.instance(), method.lower())

        # Calling the server ...
        if self.debug:
            plg_logger.log(
                message="DEBUG - Sending {} request to {}".format(
                    method.upper(), req.url().toString()
                ),
                log_level=4,
            )
        self.on_abort = False
        headers = {str(h): str(req.rawHeader(h)) for h in req.rawHeaderList()}
        if self.debug:
            for k, v in list(headers.items()):
                plg_logger.log(message="DEBUG - {}: {}".format(k, v), log_level=4)
        if method.lower() in ["post", "put"]:
            if hasattr(body, "read"):
                body = body.read()
            self.reply = func(req, body)
        else:
            self.reply = func(req)
        if self.authid:
            if self.debug:
                plg_logger.log("Update reply w/ authid: {0}".format(self.authid))
            QgsAuthManager.instance().updateNetworkReply(self.reply, self.authid)

        # necessary to trap local timeout manage by QgsNetworkAccessManager
        # calling QgsNetworkAccessManager::abortRequest
        QgsNetworkAccessManager.instance().requestTimedOut.connect(self.requestTimedOut)

        self.reply.sslErrors.connect(self.sslErrors)
        self.reply.finished.connect(self.replyFinished)
        self.reply.downloadProgress.connect(self.downloadProgress)

        # block if blocking mode otherwise return immediately
        # it's up to the caller to manage listeners in case of no blocking mode
        if not self.blocking_mode:
            return None, None

        # Call and block
        self.el = QEventLoop()
        self.reply.finished.connect(self.el.quit)

        # Catch all exceptions (and clean up requests)
        try:
            self.el.exec_(QEventLoop.ExcludeUserInputEvents)
        except Exception as err:
            plg_logger.log(
                message="Request to {} failed. Trace: {}".format(url, err),
                log_level=2,
                push=1,
            )
            raise err

        if self.reply:
            self.reply.finished.disconnect(self.el.quit)

        # emit exception in case of error
        if not self.http_call_result.ok:
            if self.http_call_result.exception and not self.exception_class:
                raise self.http_call_result.exception
            elif self.exception_class:
                raise self.exception_class(self.http_call_result.reason)
            else:
                raise RequestsException("Unknown reason")

        return self.http_call_result, self.http_call_result.content

    def downloadProgress(self, bytesReceived: int, bytesTotal: int):
        """Keep track of the download progress"""
        # plg_logger.log("downloadProgress %s of %s ..." % (bytesReceived, bytesTotal))
        pass

    def requestTimedOut(self, QNetworkReply):
        """Trap the timeout. In Async mode requestTimedOut is called after replyFinished"""
        # adapt http_call_result basing on receiving qgs timer timout signal
        self.exception_class = RequestsExceptionTimeout
        self.http_call_result.exception = RequestsExceptionTimeout("Timeout error")

    def replyFinished(self):
        err = self.reply.error()
        httpStatus = self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        httpStatusMessage = self.reply.attribute(
            QNetworkRequest.HttpReasonPhraseAttribute
        )
        self.http_call_result.status_code = httpStatus
        self.http_call_result.status = httpStatus
        self.http_call_result.status_message = httpStatusMessage
        for k, v in self.reply.rawHeaderPairs():
            self.http_call_result.headers[str(k)] = str(v)
            self.http_call_result.headers[str(k).lower()] = str(v)

        if err != QNetworkReply.NoError:
            # handle error
            # check if errorString is empty, if so, then set err string as
            # reply dump
            if re.match("(.)*server replied: $", self.reply.errorString()):
                errString = self.reply.errorString() + self.http_call_result.content
            else:
                errString = self.reply.errorString()
            # check if self.http_call_result.status_code is available (client abort
            # does not produce http.status_code)
            if self.http_call_result.status_code:
                msg = "Network error #{0}: {1}".format(
                    self.http_call_result.status_code, errString
                )
            else:
                msg = "Network error: {0}".format(errString)

            self.http_call_result.reason = msg
            self.http_call_result.ok = False
            plg_logger.log(message=msg, log_level=2, push=1)
            # set return exception
            if err == QNetworkReply.TimeoutError:
                self.http_call_result.exception = RequestsExceptionTimeout(msg)

            elif err == QNetworkReply.ConnectionRefusedError:
                self.http_call_result.exception = RequestsExceptionConnectionError(msg)

            elif err == QNetworkReply.OperationCanceledError:
                # request abort by calling NAM.abort() => cancelled by the user
                if self.on_abort:
                    self.http_call_result.exception = RequestsExceptionUserAbort(msg)
                else:
                    self.http_call_result.exception = RequestsException(msg)

            else:
                self.http_call_result.exception = RequestsException(msg)

            # overload exception to the custom exception if available
            if self.exception_class:
                self.http_call_result.exception = self.exception_class(msg)

        else:
            # Handle redirections
            redirection_url = self.reply.attribute(
                QNetworkRequest.RedirectionTargetAttribute
            )
            if redirection_url is not None and redirection_url != self.reply.url():
                if redirection_url.isRelative():
                    redirection_url = self.reply.url().resolved(redirection_url)

                msg = "Redirected from '{}' to '{}'".format(
                    self.reply.url().toString(), redirection_url.toString()
                )
                if self.debug:
                    plg_logger.log(message=f"DEBUG - {msg}", log_level=4)

                self.reply.deleteLater()
                self.reply = None
                self.request(redirection_url.toString(), headers=self.headers)

            # really end request
            else:
                msg = "Network success #{0}".format(self.reply.error())
                self.http_call_result.reason = msg
                if self.debug:
                    plg_logger.log(message=f"DEBUG - {msg}", log_level=4)

                ba = self.reply.readAll()
                self.http_call_result.content = bytes(ba)
                self.http_call_result.ok = True

        # Let's log the whole response for debugging purposes:
        if self.debug:
            plg_logger.log(
                "Got response %s %s from %s"
                % (
                    self.http_call_result.status_code,
                    self.http_call_result.status_message,
                    self.reply.url().toString()
                    if self.reply
                    else "reply has been deleted",
                )
            )
            for k, v in list(self.http_call_result.headers.items()):
                plg_logger.log("%s: %s" % (k, v))
            if len(self.http_call_result.content) < 1024:
                plg_logger.log("Payload :\n%s" % self.http_call_result.content)
            else:
                plg_logger.log("Payload is > 1 KB ...")

        # clean reply
        if self.reply is not None:
            if self.reply.isRunning():
                self.reply.close()
            if self.debug:
                plg_logger.log(message="DEBUG - Deleting reply ...", log_level=4)
            # Disconnect all slots
            self.reply.sslErrors.disconnect(self.sslErrors)
            self.reply.finished.disconnect(self.replyFinished)
            self.reply.downloadProgress.disconnect(self.downloadProgress)
            self.reply.deleteLater()
            self.reply = None
        else:
            if self.debug:
                plg_logger.log(
                    message="DEBUG - Reply was already deleted ...", log_level=4
                )

        self.finished.emit(self.http_call_result)

    def sslErrors(self, ssl_errors):
        """
        Handle SSL errors, logging them if debug is on and ignoring them
        if disable_ssl_certificate_validation is set.
        """
        if ssl_errors:
            for v in ssl_errors:
                plg_logger.log("SSL Error: %s" % v.errorString())
        if self.disable_ssl_certificate_validation:
            self.reply.ignoreSslErrors()

    def abort(self):
        """
        Handle request to cancel HTTP call
        """
        if self.reply and self.reply.isRunning():
            self.on_abort = True
            self.reply.abort()
