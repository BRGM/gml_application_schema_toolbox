#! python3  # noqa: E265

# ############################################################################
# ########## Imports ###############
# ##################################

# Standard library
import logging
from io import BytesIO
from typing import Dict

# project
from gml_application_schema_toolbox.__about__ import __title__
from gml_application_schema_toolbox.toolbelt import PlgLogger, PlgOptionsManager
from gml_application_schema_toolbox.toolbelt.network_manager import (
    NetworkAccessManager,
    RequestsException,
)

# ############################################################################
# ########## Globals ###############
# ##################################

__network_manager = None
logger = logging.getLogger(__name__)
plg_logger = PlgLogger()
plg_settings = PlgOptionsManager().get_plg_settings()

# ############################################################################
# ########## Functions #############
# ##################################


def remote_open_from_qgis(
    uri: str,
    headers: Dict[bytes, bytes] = {
        b"Accept": b"application/xml",
        b"Accept-Language": bytes(plg_settings.network_language, "utf8"),
        b"User-Agent": bytes(plg_settings.network_http_user_agent, "utf8"),
    },
) -> BytesIO:
    """Opens a remote URL using Network Acess Manager. In fact, just a shortcut.

    :param uri: URI to request
    :type uri: str
    :param headers: HTTP headers. Defaults to: \
    .. code-block:: python

        {
            b"Accept": b"application/xml",
            b"Accept-Language": bytes(settings.value("default_language", "fr"), "utf8"),
            b"User-Agent": bytes(settings.value("http_user_agent", __title__), "utf8")
            }
    :type headers: Dict[bytes, bytes], optional

    :return: response content as bytesarray or None if something went wrong
    :rtype: BytesIO
    """
    nam = NetworkAccessManager()
    try:
        response, content = nam.request(url=uri, headers=headers)
        plg_logger.log(response.status_code)
        return BytesIO(content)
    except RequestsException as err:
        logger.error(err)
        plg_logger.log(
            message="Request to {} failed. Trace: {}".format(uri, err),
            log_level=2,
            push=1,
        )
        return None
