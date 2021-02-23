#! python3  # noqa: E265

# standard library
import logging

# PyQGIS
from qgis.core import QgsMessageLog
from qgis.utils import iface

# project package
from gml_application_schema_toolbox.__about__ import __title__


# ############################################################################
# ########## Classes ###############
# ##################################


class PluginLogHandler(logging.Handler):
    def __init__(self):
        """Python logging handler supercharged with QGIS useful methods.
        """        
        pass

    @staticmethod
    def log(
        message: str,
        application: str = __title__,
        log_level: int = 0,
        push: bool = False,
    ):
        """Send messages to QGIS messages windows and to the user as a message bar. \
        Plugin name is used as title.

        :param message: message to display
        :type message: str
        :param application: name of the application sending the message. \
        Defaults to __about__.__title__
        :type application: str, optional
        :param log_level: message level. Possible values: 0 (info), 1 (warning), \
        2 (critical), 3 (success), 4 (none - grey). Defaults to 0 (info)
        :type log_level: int, optional
        :param push: also display the message in the QGIS message bar in addition to \
        the log, defaults to False
        :type push: bool, optional

        :Example:

        .. code-block:: python

            log(message="Plugin loaded - INFO", log_level=0, push=1)
            log(message="Plugin loaded - WARNING", log_level=1, push=1)
            log(message="Plugin loaded - ERROR", log_level=2, push=1)
            log(message="Plugin loaded - SUCCESS", log_level=3, push=1)
            log(message="Plugin loaded - TEST", log_level=4, push=1)
        """
        # send it to QGIS messages panel
        QgsMessageLog.logMessage(
            message=message, tag=application, notifyUser=push, level=log_level
        )

        # optionally, display message on QGIS Message bar (above the map canvas)
        if push:
            iface.messageBar().pushMessage(
                title=application,
                text=message,
                level=log_level,
                duration=(log_level + 1) * 3,
            )

    def gdal_error_handler(self, eErrClass, err_no, msg: str):
        """Shortcut to log method specific to GDAL errors.

        :param eErrClass: [description]
        :type eErrClass: [type]
        :param err_no: [description]
        :type err_no: [type]
        :param msg: error message
        :type msg: str
        """
        self.log(
            message=f"{eErrClass} {err_no}: {msg}".format(eErrClass, err_no, msg),
            log_level=2,
        )

    def emit(self, record):
        try:
            msg = self.format(record)
            QgsMessageLog.logMessage(msg, self.tag)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as err:
            QgsMessageLog.logMessage(err, self.tag, QgsMessageLog.ERROR)
            self.handleError(record)
