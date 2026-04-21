from __future__ import annotations

import hmac
import logging
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

import httpx

from .errors import ApiError, NetworkError

log = logging.getLogger("trading_bot.binance")


def _hmac_sha256(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), sha256).hexdigest()


@dataclass(frozen=True)
class BinanceFuturesClient:
    api_key: str
    api_secret: str
    base_url: str = "https://testnet.binancefuture.com"
    timeout_s: float = 10.0
    max_retries: int = 2
    backoff_ms: int = 250

    # mutable runtime state (kept off constructor API)
    _time_offset_ms: int = 0

    def _headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self.api_key}

    def sync_time(self) -> int:
        """
        Sync local timestamp with Binance serverTime.
        Stores offset (server - local) in milliseconds and returns it.
        """
        local = int(time.time() * 1000)
        server_time = int(self.time().get("serverTime"))
        offset = server_time - local
        object.__setattr__(self, "_time_offset_ms", offset)
        return offset

    def _now_ms(self) -> int:
        return int(time.time() * 1000) + int(self._time_offset_ms)

    @staticmethod
    def _redact_params(params: Mapping[str, Any]) -> dict[str, Any]:
        p = dict(params)
        if "signature" in p:
            p["signature"] = "***REDACTED***"
        return p

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        signed: bool = False,
        recv_window: int | None = None,
    ) -> dict[str, Any]:
        params = dict(params or {})
        if signed:
            params["timestamp"] = self._now_ms()
            if recv_window is not None:
                params["recvWindow"] = int(recv_window)
            # Binance expects query-string signature over URL-encoded params in order.
            query = str(httpx.QueryParams(params))
            params["signature"] = _hmac_sha256(self.api_secret, query)

        url = f"{self.base_url}{path}"
        request_log = {
            "method": method,
            "url": url,
            "path": path,
            "params": self._redact_params(params),
            "signed": signed,
        }
        log.info("api_request", extra={"event": "api_request", "request": request_log})

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    r = client.request(method=method, url=url, params=params, headers=self._headers())
            except httpx.TimeoutException as e:
                last_exc = e
                log.error(
                    "timeout",
                    extra={"event": "network_error", "error": {"type": "timeout", "attempt": attempt}},
                    exc_info=True,
                )
            except httpx.RequestError as e:
                last_exc = e
                log.error(
                    "request_error",
                    extra={
                        "event": "network_error",
                        "error": {"type": "request_error", "detail": str(e), "attempt": attempt},
                    },
                    exc_info=True,
                )
            else:
                # retry on transient HTTP statuses (429/5xx)
                if r.status_code in (418, 429) or 500 <= r.status_code <= 599:
                    if attempt < self.max_retries:
                        time.sleep((self.backoff_ms * (2**attempt)) / 1000.0)
                        continue
                break

            if attempt < self.max_retries:
                time.sleep((self.backoff_ms * (2**attempt)) / 1000.0)
                continue

            if isinstance(last_exc, httpx.TimeoutException):
                raise NetworkError("Request timed out") from last_exc
            if isinstance(last_exc, httpx.RequestError):
                raise NetworkError(str(last_exc)) from last_exc
            raise NetworkError("Request failed") from last_exc

        text = r.text
        response_log = {"status_code": r.status_code, "text": text[:10_000]}
        if r.headers.get("content-type", "").startswith("application/json"):
            try:
                json_payload = r.json()
                response_log["json"] = json_payload
            except Exception:
                pass

        if r.status_code >= 400:
            log.error(
                "api_error",
                extra={"event": "api_error", "request": request_log, "response": response_log},
            )
            payload = response_log.get("json") if isinstance(response_log.get("json"), dict) else {}
            msg = payload.get("msg") or f"HTTP {r.status_code}"
            raise ApiError(msg, status_code=r.status_code, payload=payload)

        log.info(
            "api_response",
            extra={"event": "api_response", "request": request_log, "response": response_log},
        )
        if "json" in response_log and isinstance(response_log["json"], dict):
            return response_log["json"]

        # Binance always returns JSON for these endpoints; keep a safe fallback.
        return {"raw": text}

    def ping(self) -> dict[str, Any]:
        return self._request("GET", "/fapi/v1/ping")

    def time(self) -> dict[str, Any]:
        return self._request("GET", "/fapi/v1/time")

    def exchange_info(self) -> dict[str, Any]:
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def new_order(self, *, params: Mapping[str, Any]) -> dict[str, Any]:
        # POST /fapi/v1/order must be signed
        return self._request("POST", "/fapi/v1/order", params=params, signed=True)

    def new_algo_order(self, *, params: Mapping[str, Any]) -> dict[str, Any]:
        # POST /fapi/v1/algoOrder must be signed
        return self._request("POST", "/fapi/v1/algoOrder", params=params, signed=True)

    def new_order_with_window(self, *, params: Mapping[str, Any], recv_window: int | None) -> dict[str, Any]:
        return self._request("POST", "/fapi/v1/order", params=params, signed=True, recv_window=recv_window)

    def new_algo_order_with_window(self, *, params: Mapping[str, Any], recv_window: int | None) -> dict[str, Any]:
        return self._request("POST", "/fapi/v1/algoOrder", params=params, signed=True, recv_window=recv_window)
