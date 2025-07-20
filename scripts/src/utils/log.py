"""Logging configuration."""

import logging
import os


class ExcludeLockFilter(logging.Filter):
    def filter(self, record):
        return ".lock" not in record.getMessage()


def get_logging_config(log_file):
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(module)s - %(levelname)s"
                          " - %(message)s",
            },
        },
        "filters": {
            "exclude_lock": {
                "()": ExcludeLockFilter,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "default",
                "filters": ["exclude_lock"],
            },
            "file": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "default",
                "filename": log_file,
                "filters": ["exclude_lock"],
                "mode": "a",
            },
        },
        "root": {
            "level": "DEBUG" if os.getenv("LOGGING_DEBUG") else "INFO",
            "handlers": ["console", "file"],
        },
    }
