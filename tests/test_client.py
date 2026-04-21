import json
import types

import httpx
import pytest

from trading_bot.bot.client import BinanceFuturesClient
from trading_bot.bot.errors import ApiError, NetworkError


class _Resp:
    def __init__(self, *, status_code: int, json_payload=None, text=""):
        self.status_code = status_code
        self._json_payload = json_payload
        self.text = text or (json.dumps(json_payload) if json_payload is not None else "")
        self.headers = {"content-type": "application/json"}

    def json(self):
        if self._json_payload is None:
            raise ValueError("no json")
        return self._json_payload


class _ClientCtx:
    def __init__(self, handler):
        self._handler = handler

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def request(self, method, url, params=None, headers=None):
        return self._handler(method=method, url=url, params=params or {}, headers=headers or {})


def test_signed_request_includes_timestamp_and_signature(monkeypatch):
    captured = {}

    def handler(method, url, params, headers):
        captured["method"] = method
        captured["url"] = url
        captured["params"] = dict(params)
        captured["headers"] = dict(headers)
        return _Resp(status_code=200, json_payload={"ok": True})

    monkeypatch.setattr(httpx, "Client", lambda timeout=None: _ClientCtx(handler))

    c = BinanceFuturesClient(api_key="k", api_secret="s", base_url="https://example.com")
    c.new_order(params={"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "quantity": "1"})

    assert captured["method"] == "POST"
    assert captured["headers"]["X-MBX-APIKEY"] == "k"
    assert "timestamp" in captured["params"]
    assert "signature" in captured["params"]


def test_api_error_maps_to_ApiError(monkeypatch):
    def handler(method, url, params, headers):
        return _Resp(status_code=400, json_payload={"code": -1, "msg": "bad"})

    monkeypatch.setattr(httpx, "Client", lambda timeout=None: _ClientCtx(handler))
    c = BinanceFuturesClient(api_key="k", api_secret="s", base_url="https://example.com")
    with pytest.raises(ApiError) as e:
        c.new_order(params={"symbol": "BTCUSDT"})
    assert e.value.status_code == 400
    assert e.value.payload.get("msg") == "bad"


def test_network_error_maps_to_NetworkError(monkeypatch):
    class _BoomClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, method, url, params=None, headers=None):
            raise httpx.RequestError("boom", request=types.SimpleNamespace(url=url))

    monkeypatch.setattr(httpx, "Client", _BoomClient)
    c = BinanceFuturesClient(api_key="k", api_secret="s", base_url="https://example.com")
    with pytest.raises(NetworkError):
        c.ping()

