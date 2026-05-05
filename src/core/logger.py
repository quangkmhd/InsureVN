import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from langfuse import get_client
except ImportError:
    get_client = None


STANDARD_LOG_ATTRS = {
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


def _extra_attributes(record: logging.LogRecord) -> dict:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in STANDARD_LOG_ATTRS and not key.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    """Production-grade JSON formatter for logs."""

    def format(self, record):
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
        log_record.update(_extra_attributes(record))

        return json.dumps(log_record, ensure_ascii=False)


class LangfuseLogHandler(logging.Handler):
    """Mirror Python log records into Langfuse as span observations."""

    _ignored_prefixes = ("langfuse", "httpx", "httpcore", "urllib3")

    def emit(self, record: logging.LogRecord) -> None:
        if get_client is None or record.name.startswith(self._ignored_prefixes):
            return

        try:
            langfuse_client = get_client()
            message = record.getMessage()
            metadata = {
                "logger": record.name,
                "level": record.levelname,
                "pathname": record.pathname,
                "lineno": record.lineno,
                "function": record.funcName,
                **_extra_attributes(record),
            }
            if record.exc_info:
                metadata["exception"] = self.format(record)

            with langfuse_client.start_as_current_observation(
                as_type="span",
                name=f"log.{record.name}",
            ) as observation:
                observation.update(
                    input={"message": message},
                    output=None,
                    level=self._langfuse_level(record.levelno),
                    status_message=message[:500],
                    metadata=metadata,
                )
        except Exception:
            self.handleError(record)

    @staticmethod
    def _langfuse_level(levelno: int) -> str:
        if levelno >= logging.ERROR:
            return "ERROR"
        if levelno >= logging.WARNING:
            return "WARNING"
        if levelno <= logging.DEBUG:
            return "DEBUG"
        return "DEFAULT"


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

        langfuse_handler = LangfuseLogHandler(level=level)
        logger.addHandler(langfuse_handler)

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
