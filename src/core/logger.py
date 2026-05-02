import logging
import sys
import json
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """Production-grade JSON formatter for logs."""
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Add any extra attributes passed in the 'extra' dict
        if hasattr(record, "extra"):
            log_record.update(record.extra)
            
        return json.dumps(log_record, ensure_ascii=False)

def get_logger(
    name: str,
    stream=None,
    log_file: str | None = None,
    level: int = logging.INFO,
    json_format: bool = True
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
                log_path, 
                maxBytes=10 * 1024 * 1024, 
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
    return logger
