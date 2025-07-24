import logging
import os
from pythonjsonlogger import jsonlogger

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            log_record['timestamp'] = record.created
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": CustomJsonFormatter,
            "format": "%(timestamp)s %(level)s %(name)s %(message)s %(pathname)s %(lineno)d",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "uvicorn.error": {"level": LOG_LEVEL, "propagate": True},
        "uvicorn.access": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "": {"handlers": ["console"], "level": LOG_LEVEL}, # Root logger
    },
}
