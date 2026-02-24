"""Lightweight logger for the customer health agent."""
import logging
import os
import time
from contextlib import contextmanager

_stats = {
    "llm_calls": 0,
    "mcp_calls": 0,
    "total_tokens": 0,
    "start_time": None,
}


class _Formatter(logging.Formatter):
    """Custom formatter: [node_name] HH:MM:SS message."""

    def format(self, record):
        node = getattr(record, "node", "main")
        ts = time.strftime("%H:%M:%S", time.localtime(record.created))
        return f"[{node}] {ts} {record.getMessage()}"


def get_logger(name: str) -> logging.Logger:
    """Create a logger with custom formatting."""
    logger = logging.getLogger(f"health.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_Formatter())
        logger.addHandler(handler)
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))
    return logger


@contextmanager
def log_time(label: str, logger: logging.Logger = None):
    """Context manager that measures and logs elapsed time."""
    start = time.time()
    yield
    elapsed = time.time() - start
    msg = f"{label} completed in {elapsed:.2f}s"
    log = logger or get_logger("timer")
    log.info(msg, extra={"node": "timer"})


def track(key: str, value: int = 1):
    """Increment a stats counter."""
    if key in _stats and isinstance(_stats[key], (int, float)):
        _stats[key] += value


def start_run():
    """Mark the start of a run."""
    _stats["start_time"] = time.time()
    _stats["llm_calls"] = 0
    _stats["mcp_calls"] = 0
    _stats["total_tokens"] = 0


def print_summary():
    """Print run summary stats."""
    elapsed = time.time() - _stats["start_time"] if _stats["start_time"] else 0
    log = get_logger("summary")
    log.info("--- Run Summary ---", extra={"node": "summary"})
    log.info(f"LLM calls: {_stats['llm_calls']}", extra={"node": "summary"})
    log.info(f"MCP calls: {_stats['mcp_calls']}", extra={"node": "summary"})
    log.info(f"Total time: {elapsed:.2f}s", extra={"node": "summary"})
