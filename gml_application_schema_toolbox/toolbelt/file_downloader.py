#! python3  # noqa: E265

"""
    Functions used to manage network requests (remote files, etc.)
"""

# Standard library
import logging

# PyQGIS
from qgis.core import QgsFileDownloader
from qgis.PyQt.QtCore import QEventLoop, QUrl

# project
from gml_application_schema_toolbox.toolbelt.log_handler import PlgLogger

# ############################################################################
# ########## Globals ###############
# ##################################

logger = logging.getLogger(__name__)
plg_logger = PlgLogger()

# ############################################################################
# ########## Functions #############
# ##################################


def get_from_http(uri: str, output_path: str) -> str:
    """Download a file from a remote web server accessible through HTTP.

    :param uri: web URL to the QGIS project
    :type uri: str
    :param output_path: path to the local file
    :type output_path: str

    :return: output path
    :rtype: str
    """
    msg_log = f"Downloading file from {uri} to {output_path}"
    logger.debug(msg_log)
    plg_logger.log(msg_log)
    # download it
    loop = QEventLoop()
    project_download = QgsFileDownloader(
        url=QUrl(uri), outputFileName=output_path, delayStart=True
    )
    project_download.downloadExited.connect(loop.quit)
    project_download.startDownload()
    loop.exec_()

    plg_logger.log(message=f"Download of {uri} succeedeed", log_level=3)
    return output_path
