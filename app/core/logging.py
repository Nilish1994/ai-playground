import logging
import logging.config
from typing import Any


def configure_logging(level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.json.JsonFormatter",
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["default"], "level": level},
            "loggers": {
                "uvicorn.access": {"handlers": ["default"], "level": level, "propagate": False}
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_context(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}
