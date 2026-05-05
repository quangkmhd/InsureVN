import logging
from unittest.mock import MagicMock, patch

from src.core.logger import LangfuseLogHandler, get_logger


def test_logger_creation():
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"
    assert logger.level == logging.INFO


def test_langfuse_log_handler_emits_log_observation():
    record = logging.LogRecord(
        name="test_module",
        level=logging.ERROR,
        pathname=__file__,
        lineno=10,
        msg="boom",
        args=(),
        exc_info=None,
    )
    record.component = "unit-test"

    fake_observation = MagicMock()
    fake_context = MagicMock()
    fake_context.__enter__.return_value = fake_observation
    fake_context.__exit__.return_value = None
    fake_client = MagicMock()
    fake_client.start_as_current_observation.return_value = fake_context

    with patch("src.core.logger.get_client", return_value=fake_client):
        LangfuseLogHandler().emit(record)

    fake_client.start_as_current_observation.assert_called_once()
    _, kwargs = fake_client.start_as_current_observation.call_args
    assert kwargs["as_type"] == "span"
    assert kwargs["name"] == "log.test_module"
    fake_observation.update.assert_called_once()
    _, update_kwargs = fake_observation.update.call_args
    assert update_kwargs["level"] == "ERROR"
    assert update_kwargs["status_message"] == "boom"
    assert update_kwargs["input"] == {"message": "boom"}
    assert update_kwargs["metadata"]["component"] == "unit-test"


def test_get_logger_attaches_langfuse_log_handler():
    logger = get_logger("test_module_with_langfuse")

    assert any(isinstance(handler, LangfuseLogHandler) for handler in logger.handlers)
