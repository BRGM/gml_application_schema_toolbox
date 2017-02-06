# -*- coding: utf-8 -*-

import logging
from qgis.core import QgsMessageLog
from gml_application_schema_toolbox import name


def log(msg):
    QgsMessageLog.logMessage(msg, name())


def gdal_error_handler(eErrClass, err_no, msg):
    log('{} {}: {}'.format(eErrClass, err_no, msg))


class QgsMessageLogHandler(logging.Handler):

    def __init__(self, tag=None):
        super(QgsMessageLogHandler, self).__init__()
        self.tag = tag

    def emit(self, record):
        try:
            msg = self.format(record)
            QgsMessageLog.logMessage(msg, self.tag)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


owslib_logger = logging.getLogger('owslib')
owslib_logger.setLevel(logging.DEBUG)

owslib_handler = None
for handler in owslib_logger.handlers:
    if handler.__class__.__name__ == QgsMessageLogHandler.__name__:
        owslib_handler = handler
        break
if owslib_handler is None:
    owslib_handler = QgsMessageLogHandler(name())
    owslib_handler.setLevel(logging.DEBUG)
    owslib_logger.addHandler(owslib_handler)
