"""
Structured, secret-redacting logger for AI Financial Intelligence Platform.
Never exposes API keys or sensitive financial credentials in logs.
"""
import logging
import sys
import re

SENSITIVE_PATTERNS = [
    re.compile(r"gsk_[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"key=([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),
    re.compile(r"bearer\s+([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),
]


class SecretRedactingFormatter(logging.Formatter):
    """Custom logging formatter that scrubs API keys and bearer tokens."""
    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        redacted = original
        for pattern in SENSITIVE_PATTERNS:
            redacted = pattern.sub("[REDACTED_SECRET]", redacted)
        return redacted


def get_logger(name: str) -> logging.Logger:
    """Returns a configured logger instance with secret redaction."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            SecretRedactingFormatter(
                fmt="%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
