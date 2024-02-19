"""Configured application logger."""

import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger as _logger

from app.settings import settings

if TYPE_CHECKING:  # To avoid circular import
    from loguru import Logger


# This code copied from loguru docs, ignoring all linters warnings
# https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
class InterceptHandler(logging.Handler):
    def emit(self, record):  # type: ignore
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:  # noqa: WPS352, WPS609
            frame = frame.f_back  # type: ignore [assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logger() -> "Logger":
    # Remove every logger's handlers and propagate to root logger
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    # Интерсептор для хэндлеров logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0)

    # Путь к файлу, в который будут писаться логи
    log_file_path = "/home/Hohlov/wb_api_service/logfile.log"

    # Настройка loguru
    _logger.configure(
        handlers=[
            {
                # Пишем в файл
                "sink": log_file_path,
                "level": logging.DEBUG if settings.debug else logging.INFO,
                "enqueue": True,
                "rotation": "1 week",  # Ротация файла каждую неделю
                "retention": "1 month",  # Сохранение записей в течение месяца
                "format": "{time:DD-MM-YYYY HH:mm:ss} | {level} | {message}",
            }
        ],
    )

    return _logger

logger = setup_logger()
