import logging
from logging import Logger


def _make_logger() -> Logger:
    logger = logging.getLogger("reqless")
    formatter = logging.Formatter(
        "%(asctime)s | PID %(process)d | [%(levelname)s] %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.FATAL)

    return logger


logger = _make_logger()

__all__ = [
    "logger",
]
