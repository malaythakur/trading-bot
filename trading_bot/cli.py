from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from trading_bot.bot.client import BinanceFuturesClient
from trading_bot.bot.errors import ApiError, NetworkError, TradingBotError, ValidationError
from trading_bot.bot.logging_config import TRACE_ID, setup_logging
from trading_bot.bot.orders import OrderService
from trading_bot.bot.validators import OrderInput


def _make_client() -> BinanceFuturesClient:
    load_dotenv(override=False)

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    base_url = os.getenv("BINANCE_FUTURES_BASE_URL", "https://testnet.binancefuture.com")

    if not api_key or not api_secret:
        raise ValidationError(
            "Missing BINANCE_API_KEY / BINANCE_API_SECRET. Set env vars or create a .env file."
        )

    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret, base_url=base_url)


def _setup_logs(log_file: str | None) -> Path:
    path = Path(log_file) if log_file else Path("logs") / "trading_bot.log"
    setup_logging(path)
    return path


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _cmd_health(args: argparse.Namespace) -> int:
    log_path = _setup_logs(args.log_file)
    try:
        TRACE_ID.set(args.trace_id or str(uuid.uuid4()))
        client = _make_client()
        if args.use_server_time:
            client.sync_time()
        print("ping:")
        _print_json(client.ping())
        print("\ntime:")
        _print_json(client.time())
        print(f"\nOK. Logs: {log_path}")
        return 0
    except TradingBotError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 5


def _cmd_order(args: argparse.Namespace) -> int:
    log_path = _setup_logs(args.log_file)
    try:
        TRACE_ID.set(args.trace_id or str(uuid.uuid4()))
        order = OrderInput.parse(
            symbol=args.symbol,
            side=args.side,
            order_type=args.type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
            client_order_id=args.client_order_id,
        )
        client = _make_client()
        if args.use_server_time:
            client.sync_time()
        svc = OrderService(client)

        if args.dry_run:
            endpoint, params = svc.build_request(order)
            payload = {"dry_run": True, "request": order.to_public_dict(), "endpoint": endpoint, "params": params}
            if args.output == "json":
                _print_json(payload)
            else:
                print("=== Order Request Summary ===")
                _print_json(order.to_public_dict())
                print("\n=== Dry Run (no order sent) ===")
                _print_json({"endpoint": endpoint, "params": params})
                print(f"\nSUCCESS: dry-run completed. Logs: {log_path}")
            return 0

        if args.output != "json":
            print("=== Order Request Summary ===")
            _print_json(order.to_public_dict())

        resp = svc.place_order(order, recv_window=args.recv_window)

        if "algoId" in resp:
            response_view = {
                "algoId": resp.get("algoId"),
                "algoStatus": resp.get("algoStatus"),
                "orderType": resp.get("orderType"),
                "triggerPrice": resp.get("triggerPrice"),
                "raw": resp,
            }
        else:
            response_view = {
                "orderId": resp.get("orderId"),
                "status": resp.get("status"),
                "executedQty": resp.get("executedQty"),
                "avgPrice": resp.get("avgPrice"),
                "raw": resp,
            }

        if args.output == "json":
            _print_json({"success": True, "request": order.to_public_dict(), "response": response_view})
        else:
            print("\n=== Order Response ===")
            _print_json(response_view)
            print(f"\nSUCCESS: order placed. Logs: {log_path}")
        return 0
    except ValidationError as e:
        print(f"INPUT ERROR: {e}", file=sys.stderr)
        return 2
    except ApiError as e:
        print(f"API ERROR: {e} (status={e.status_code})", file=sys.stderr)
        if e.payload:
            print(json.dumps(e.payload, indent=2), file=sys.stderr)
        return 3
    except NetworkError as e:
        print(f"NETWORK ERROR: {e}", file=sys.stderr)
        return 4
    except TradingBotError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 5


def main() -> None:
    parser = argparse.ArgumentParser(prog="trading-bot", description="Binance Futures Testnet order CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_health = sub.add_parser("health", help="Connectivity check (ping/time)")
    p_health.add_argument("--log-file", default=None, help="Write logs to this file")
    p_health.add_argument("--use-server-time", action="store_true", help="Sync timestamp with Binance server time")
    p_health.add_argument("--trace-id", default=None, help="Attach a trace id to all logs for this run")
    p_health.set_defaults(func=_cmd_health)

    p_order = sub.add_parser("order", help="Place an order (MARKET/LIMIT/STOP_MARKET/STOP)")
    p_order.add_argument("--symbol", "-s", required=True, help="e.g. BTCUSDT")
    p_order.add_argument("--side", required=True, help="BUY or SELL")
    p_order.add_argument("--type", required=True, help="MARKET, LIMIT, STOP_MARKET, or STOP")
    p_order.add_argument("--quantity", "-q", required=True, help="Order quantity (base asset units)")
    p_order.add_argument("--price", default=None, help="Required for LIMIT and STOP")
    p_order.add_argument("--stop-price", dest="stop_price", default=None, help="Required for STOP_MARKET and STOP")
    p_order.add_argument("--client-order-id", default=None, help="Idempotency id (newClientOrderId/clientAlgoId)")
    p_order.add_argument("--recv-window", type=int, default=None, help="recvWindow in ms (signed endpoints)")
    p_order.add_argument("--use-server-time", action="store_true", help="Sync timestamp with Binance server time")
    p_order.add_argument("--trace-id", default=None, help="Attach a trace id to all logs for this run")
    p_order.add_argument("--dry-run", action="store_true", help="Validate and print request without sending")
    p_order.add_argument("--output", choices=["pretty", "json"], default="pretty", help="stdout format")
    p_order.add_argument("--log-file", default=None, help="Write logs to this file")
    p_order.set_defaults(func=_cmd_order)

    args = parser.parse_args()
    code = int(args.func(args))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
