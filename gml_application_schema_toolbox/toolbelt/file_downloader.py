#! python3  # noqa: E265

"""
    Functions used to manage network requests (remote files, etc.)
"""

# Standard library
import logging
from pathlib import Path

# PyQGIS
from qgis.core import QgsFileDownloader
from qgis.PyQt.QtCore import QEventLoop, QUrl

# ############################################################################
# ########## Globals ###############
# ##################################

logger = logging.getLogger(__name__)


# ############################################################################
# ########## Functions #############
# ##################################


def get_from_http(uri: str, output_path: str):
    """Download a file from a remote web server accessible through HTTP.

    :param uri: web URL to the QGIS project
    :type uri: str
    :param output_path: [description]
    :type output_path: str
    """
    # download it
    loop = QEventLoop()
    project_download = QgsFileDownloader(
        url=QUrl(uri), outputFileName=output_path, delayStart=True
    )
    project_download.downloadExited.connect(loop.quit)
    project_download.startDownload()
    loop.exec_()

    return output_path
