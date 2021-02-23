#! python3  # noqa: E265

"""
    Functions used to manage network requests (remote files, etc.)
"""

# Standard library
import logging
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

# PyQGIS
from qgis.core import QgsFileDownloader
from qgis.PyQt.QtCore import (
    QDir,
    QEventLoop,
    QFile,
    QFileInfo,
    QIODevice,
    QTemporaryDir,
    QTemporaryFile,
    QUrl,
)

# ############################################################################
# ########## Globals ###############
# ##################################

logger = logging.getLogger(__name__)


# ############################################################################
# ########## Functions #############
# ##################################

@lru_cache()
def read_from_http(uri: str, cache_folder: Path):
    """Read a QGIS project stored into on a remote web server accessible through HTTP.

    :param uri: web URL to the QGIS project
    :type uri: str

    :return: a tuple with XML document and the filepath.
    :rtype: Tuple[QtXml.QDomDocument, str]
    """
    # get filename from URL parts
    parsed = urlparse(uri)
    if not parsed.path.rpartition("/")[2].endswith((".qgs", ".qgz")):
        raise ValueError(
            "URI doesn't ends with QGIS project extension (.qgs or .qgz): {}".format(
                uri
            )
        )
    cached_filepath = cache_folder / parsed.path.rpartition("/")[2]

    # download it
    loop = QEventLoop()
    project_download = QgsFileDownloader(
        url=QUrl(uri), outputFileName=str(cached_filepath.resolve()), delayStart=True
    )
    project_download.downloadExited.connect(loop.quit)
    project_download.startDownload()
    loop.exec_()

    return read_from_file(str(cached_filepath.resolve()))
