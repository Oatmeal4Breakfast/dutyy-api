from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import structlog

from src.config import ENV

if TYPE_CHECKING:
    from structlog.dev import ConsoleRenderer
    from structlog.processors import JSONRenderer

    from src.config import Config


def config_logger(config: Config) -> None:
    """Configures structlog based on env vars"""
    if config.env == ENV.DEVELOPMENT:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    shared_processers: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper("iso"),
    ]

    renderer: ConsoleRenderer | JSONRenderer = (
        structlog.dev.ConsoleRenderer()
        if config.env == ENV.DEVELOPMENT
        else structlog.processors.JSONRenderer()
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processers,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(stream_handler)

    structlog.configure(
        processors=[
            *shared_processers,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(min_level=log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=config.env == ENV.PRODUCTION,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.getLogger(name)
