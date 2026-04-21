from __future__ import annotations


class TradingBotError(Exception):
    """Base domain exception."""


class ValidationError(TradingBotError):
    """Invalid user input or unsupported parameters."""


class ApiError(TradingBotError):
    """Binance API returned an error response."""

    def __init__(self, message: str, *, status_code: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class NetworkError(TradingBotError):
    """Transport-level errors (timeouts, DNS, connection)."""
