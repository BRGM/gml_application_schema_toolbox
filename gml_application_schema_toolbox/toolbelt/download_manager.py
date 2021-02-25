#! python3  # noqa: E265

"""
    Functions used to manage network requests (remote files, etc.)
"""

# Standard library
import logging
from pathlib import Path
from urllib.parse import urlparse

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


def get_from_http(uri: str, output_path: str, cache_folder: Path = None):
    """Download a file from a remote web server accessible through HTTP.

    :param uri: web URL to the QGIS project
    :type uri: str
    :param output_path: [description]
    :type output_path: str
    :param cache_folder: [description], defaults to None
    :type cache_folder: Path, optional

    :return: a tuple with XML document and the filepath.
    :rtype: Tuple[QtXml.QDomDocument, str]
    """
    # get filename from URL parts
    # parsed = urlparse(uri)
    # if cache_folder is not None:
    #     cached_filepath = cache_folder / parsed.path.rpartition("/")[2]
    # else:
    #     cached_filepath = None

    # download it
    loop = QEventLoop()
    project_download = QgsFileDownloader(
        url=QUrl(uri), outputFileName=output_path, delayStart=True
    )
    project_download.downloadExited.connect(loop.quit)
    project_download.startDownload()
    loop.exec_()

    return output_path
