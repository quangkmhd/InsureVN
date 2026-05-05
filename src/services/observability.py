"""Shared Langfuse and debug logging helpers for service-layer operations."""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from langfuse import get_client, observe

from src.core.logger import get_logger

P = ParamSpec("P")
R = TypeVar("R")
_SERVICE_METADATA_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "service_metadata_context",
    default=None,
)


def add_current_service_metadata(metadata: dict[str, Any]) -> None:
    """Attach sanitized metadata to the active service observation."""
    current_metadata = _SERVICE_METADATA_CONTEXT.get()
    if current_metadata is None:
        _update_current_span(metadata=metadata)
        return

    current_metadata.update(metadata)


def service_observe(
    *,
    name: str,
    component: str,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Trace a service operation with Langfuse and sanitized debug logs.

    Args:
        name: Descriptive Langfuse observation name.
        component: Service component name for logs and trace metadata.

    Returns:
        Decorator that wraps synchronous or asynchronous service callables.
    """
    service_logger = get_logger(f"src.services.{component}", level=logging.DEBUG)

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                started_at = time.perf_counter()
                metadata_token = _SERVICE_METADATA_CONTEXT.set({})
                try:
                    _debug_started(
                        service_logger=service_logger,
                        name=name,
                        component=component,
                        func=func,
                        args=args,
                        kwargs=kwargs,
                    )
                    result = await func(*args, **kwargs)
                except Exception as exc:
                    _debug_failed(
                        service_logger=service_logger,
                        name=name,
                        component=component,
                        func=func,
                        started_at=started_at,
                        exc=exc,
                        extra_metadata=_SERVICE_METADATA_CONTEXT.get() or {},
                    )
                    raise
                else:
                    _debug_completed(
                        service_logger=service_logger,
                        name=name,
                        component=component,
                        func=func,
                        started_at=started_at,
                        result=result,
                        extra_metadata=_SERVICE_METADATA_CONTEXT.get() or {},
                    )
                    return result
                finally:
                    _SERVICE_METADATA_CONTEXT.reset(metadata_token)

            return observe(
                name=name,
                as_type="span",
                capture_input=False,
                capture_output=False,
            )(async_wrapper)

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            started_at = time.perf_counter()
            metadata_token = _SERVICE_METADATA_CONTEXT.set({})
            try:
                _debug_started(
                    service_logger=service_logger,
                    name=name,
                    component=component,
                    func=func,
                    args=args,
                    kwargs=kwargs,
                )
                result = func(*args, **kwargs)
            except Exception as exc:
                _debug_failed(
                    service_logger=service_logger,
                    name=name,
                    component=component,
                    func=func,
                    started_at=started_at,
                    exc=exc,
                    extra_metadata=_SERVICE_METADATA_CONTEXT.get() or {},
                )
                raise

            else:
                _debug_completed(
                    service_logger=service_logger,
                    name=name,
                    component=component,
                    func=func,
                    started_at=started_at,
                    result=result,
                    extra_metadata=_SERVICE_METADATA_CONTEXT.get() or {},
                )
                return result
            finally:
                _SERVICE_METADATA_CONTEXT.reset(metadata_token)

        return observe(
            name=name,
            as_type="span",
            capture_input=False,
            capture_output=False,
        )(wrapper)

    return decorator


def _debug_started(
    *,
    service_logger: logging.Logger,
    name: str,
    component: str,
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    input_summary = _summarize_call(args=args, kwargs=kwargs)
    _update_current_span(
        input=input_summary,
        metadata=_metadata(component=component, name=name, func=func),
    )
    service_logger.debug(
        "Service operation started",
        extra={
            "component": component,
            "operation": name,
            "function": _function_name(func),
            "input_summary": input_summary,
        },
    )


def _debug_completed(
    *,
    service_logger: logging.Logger,
    name: str,
    component: str,
    func: Callable[..., Any],
    started_at: float,
    result: Any,
    extra_metadata: dict[str, Any],
) -> None:
    duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    output_summary = _summarize_value(result)
    _update_current_span(
        output=output_summary,
        metadata={
            **_metadata(component=component, name=name, func=func),
            **extra_metadata,
            "duration_ms": duration_ms,
        },
    )
    service_logger.debug(
        "Service operation completed",
        extra={
            "component": component,
            "operation": name,
            "function": _function_name(func),
            "duration_ms": duration_ms,
            "output_summary": output_summary,
        },
    )


def _debug_failed(
    *,
    service_logger: logging.Logger,
    name: str,
    component: str,
    func: Callable[..., Any],
    started_at: float,
    exc: Exception,
    extra_metadata: dict[str, Any],
) -> None:
    duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    _update_current_span(
        metadata={
            **_metadata(component=component, name=name, func=func),
            **extra_metadata,
            "duration_ms": duration_ms,
            "error_type": type(exc).__name__,
        },
        level="ERROR",
        status_message=str(exc)[:500],
    )
    service_logger.error(
        "Service operation failed",
        extra={
            "component": component,
            "operation": name,
            "function": _function_name(func),
            "duration_ms": duration_ms,
            "error_type": type(exc).__name__,
        },
        exc_info=True,
    )


def _metadata(
    *,
    component: str,
    name: str,
    func: Callable[..., Any],
) -> dict[str, str]:
    return {
        "component": component,
        "operation": name,
        "function": _function_name(func),
    }


def _function_name(func: Callable[..., Any]) -> str:
    return func.__qualname__.split("<locals>.")[-1]


def _update_current_span(**kwargs: Any) -> None:
    try:
        get_client().update_current_span(**kwargs)
    except Exception:
        return


def _summarize_call(
    *,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    return {
        "args": [_summarize_value(arg) for arg in args],
        "kwargs": {
            key: _summarize_value(value)
            for key, value in sorted(kwargs.items(), key=lambda item: item[0])
        },
    }


def _summarize_value(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"type": "str", "length": len(value)}
    if isinstance(value, dict):
        keys = sorted(str(key) for key in value)[:20]
        return {"type": "dict", "size": len(value), "keys": keys}
    if isinstance(value, (list, tuple, set, frozenset)):
        return {"type": type(value).__name__, "size": len(value)}
    if isinstance(value, (int, float, bool)) or value is None:
        return {"type": type(value).__name__, "value": value}
    if hasattr(value, "__class__"):
        return {"type": value.__class__.__name__}
    return {"type": type(value).__name__}
