from __future__ import annotations
import logging
import structlog
from typing import TYPE_CHECKING

from src.config import ENV

if TYPE_CHECKING:
    from src.config import Config


def config_logger(config: Config) -> None:
    """Configures structlog based on env vars"""
    if config.env == ENV.DEVELOPMENT:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    stream_handler = logging.StreamHandler()

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(stream_handler)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
        ]
    )
