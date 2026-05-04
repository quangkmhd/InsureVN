import logging

from src.core.logger import get_logger


def test_logger_creation():
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"
    assert logger.level == logging.INFO
