# -*- coding: utf-8 -*-

import os
from qgis.PyQt.QtCore import QSettings
from osgeo import gdal


class qgis_proxy_settings():

    def __enter__(self):
        # keep previous config
        self.http_proxy = os.environ.get("http_proxy")
        self.https_proxy = os.environ.get("https_proxy")
        self.no_proxy = os.environ.get("no_proxy")
        self.gdal_http_proxy = gdal.GetConfigOption("GDAL_HTTP_PROXY")
        self.gdal_http_proxyuserpwd = gdal.GetConfigOption("GDAL_HTTP_PROXYUSERPWD")

        # apply QGIS proxy settings
        settings = QSettings()
        enabled = bool(settings.value("proxy/proxyEnabled", False))
        type = settings.value("proxy/proxyType", "")
        host = settings.value("proxy/proxyHost", "")
        port = settings.value("proxy/proxyPort", "")
        user = settings.value("proxy/proxyUser", "")
        password = settings.value("proxy/proxyPassword", "")
        excludes = settings.value("proxy/proxyExcludedUrls", "")
        if hasattr(excludes, 'isNull') and excludes.isNull():
            excludes = []
        else:
            excludes = excludes.split("|")

        http_proxy = ""
        no_proxy = ""
        gdal_http_proxy = ""
        gdal_http_proxyuserpwd = ""

        if enabled:
            if type == "HttpProxy":
                credentials = ""
                if user != "":
                    credentials = "{}:{}@".format(user, password)
                http_proxy = "http://{}{}:{}".format(credentials, host, port)
                no_proxy = ",".join(excludes)

            os.environ["http_proxy"] = http_proxy
            os.environ["https_proxy"] = http_proxy
            os.environ["no_proxy"] = no_proxy

            gdal_http_proxy = "{}:{}".format(host, port)
            gdal.SetConfigOption('GDAL_HTTP_PROXY', gdal_http_proxy)
            if user != "":
                gdal_http_proxyuserpwd = "{}:{}".format(user, password)
                gdal.SetConfigOption('GDAL_HTTP_PROXYUSERPWD', gdal_http_proxyuserpwd)

    def __exit__(self, type, value, tb):
        # restore previous settings
        if self.http_proxy is not None:
            os.environ['http_proxy'] = self.http_proxy
            os.environ['http_proxy'] = self.http_proxy
        else:
            os.environ.pop('http_proxy', None)
            os.environ.pop('https_proxy', None)
        if self.no_proxy is not None:
            os.environ['no_proxy'] = self.no_proxy
        else:
            os.environ.pop('no_proxy', None)
        gdal.SetConfigOption("GDAL_HTTP_PROXY", self.gdal_http_proxy)
        gdal.SetConfigOption("GDAL_HTTP_PROXYUSERPWD", self.gdal_http_proxyuserpwd)
