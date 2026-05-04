import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """Production-grade JSON formatter for logs."""

    def format(self, record):
        # Standard attributes to exclude from metadata
        standard_attrs = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "message",
        }

        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Automatically add all "extra" attributes
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_record[key] = value

        return json.dumps(log_record, ensure_ascii=False)


def get_logger(
    name: str,
    stream=None,
    log_file: str | None = None,
    level: int = logging.INFO,
    json_format: bool = True,
) -> logging.Logger:
    """Returns a configured logger instance with production best practices."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(level)

        # Format selection
        if json_format:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        # Console handler (standard stderr for MCP)
        console_handler = logging.StreamHandler(stream or sys.stderr)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler with rotation (prevents disk full)
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            # 10MB per file, keep 5 backups
            file_handler = RotatingFileHandler(
                log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger
