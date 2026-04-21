import sys

import pytest

import trading_bot.cli as cli
from trading_bot.bot.errors import ApiError, NetworkError
from trading_bot.bot.validators import OrderInput


class _SvcOK:
    def __init__(self, resp):
        self._resp = resp

    def build_request(self, order: OrderInput):
        return "order", {"symbol": order.symbol, "type": order.order_type}

    def place_order(self, order: OrderInput, *, recv_window=None):
        return dict(self._resp)


def test_cli_order_prints_summary_and_success(monkeypatch, capsys, tmp_path):
    # Avoid dotenv/env requirements
    monkeypatch.setattr(cli, "_make_client", lambda: object())
    monkeypatch.setattr(cli, "OrderService", lambda _client: _SvcOK({"orderId": 7, "status": "NEW"}))

    log_file = tmp_path / "x.log"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "x",
            "order",
            "--symbol",
            "BTCUSDT",
            "--side",
            "BUY",
            "--type",
            "MARKET",
            "-q",
            "1",
            "--log-file",
            str(log_file),
        ],
    )

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "Order Request Summary" in out
    assert "SUCCESS: order placed" in out


def test_cli_dry_run_json_output(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "_make_client", lambda: object())
    monkeypatch.setattr(cli, "OrderService", lambda _client: _SvcOK({"orderId": 7, "status": "NEW"}))
    log_file = tmp_path / "x.log"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "x",
            "order",
            "--symbol",
            "BTCUSDT",
            "--side",
            "BUY",
            "--type",
            "MARKET",
            "-q",
            "1",
            "--dry-run",
            "--output",
            "json",
            "--log-file",
            str(log_file),
        ],
    )
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert '"dry_run": true' in out


def test_cli_validation_error_exit_code(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "_make_client", lambda: object())
    monkeypatch.setattr(cli, "OrderService", lambda _client: _SvcOK({"orderId": 7, "status": "NEW"}))
    log_file = tmp_path / "x.log"
    monkeypatch.setattr(
        sys,
        "argv",
        ["x", "order", "--symbol", "BTCUSDT", "--side", "NOPE", "--type", "MARKET", "-q", "1", "--log-file", str(log_file)],
    )

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert "INPUT ERROR" in err


def test_cli_api_error_exit_code(monkeypatch, capsys, tmp_path):
    class _SvcBad:
        def build_request(self, order):
            return "order", {"symbol": order.symbol, "type": order.order_type}

        def place_order(self, order, *, recv_window=None):
            raise ApiError("bad", status_code=400, payload={"msg": "bad"})

    monkeypatch.setattr(cli, "_make_client", lambda: object())
    monkeypatch.setattr(cli, "OrderService", lambda _client: _SvcBad())
    log_file = tmp_path / "x.log"
    monkeypatch.setattr(
        sys,
        "argv",
        ["x", "order", "--symbol", "BTCUSDT", "--side", "BUY", "--type", "MARKET", "-q", "1", "--log-file", str(log_file)],
    )

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 3
    err = capsys.readouterr().err
    assert "API ERROR" in err


def test_cli_network_error_exit_code(monkeypatch, capsys, tmp_path):
    class _SvcNet:
        def build_request(self, order):
            return "order", {"symbol": order.symbol, "type": order.order_type}

        def place_order(self, order, *, recv_window=None):
            raise NetworkError("down")

    monkeypatch.setattr(cli, "_make_client", lambda: object())
    monkeypatch.setattr(cli, "OrderService", lambda _client: _SvcNet())
    log_file = tmp_path / "x.log"
    monkeypatch.setattr(
        sys,
        "argv",
        ["x", "order", "--symbol", "BTCUSDT", "--side", "BUY", "--type", "MARKET", "-q", "1", "--log-file", str(log_file)],
    )

    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 4
    err = capsys.readouterr().err
    assert "NETWORK ERROR" in err

