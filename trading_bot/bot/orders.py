from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from .client import BinanceFuturesClient
from .validators import OrderInput

log = logging.getLogger("trading_bot.orders")


class OrderService:
    def __init__(self, client: BinanceFuturesClient):
        self._client = client

    @staticmethod
    def _fmt_decimal(d: Decimal) -> str:
        # Binance expects strings for decimal fields.
        return format(d, "f")

    def build_request(self, order: OrderInput) -> tuple[str, dict[str, Any]]:
        if order.order_type == "STOP_MARKET":
            # Binance changed conditional orders to Algo Order endpoints (error -4120 on /order).
            params: dict[str, Any] = {
                "algoType": "CONDITIONAL",
                "symbol": order.symbol,
                "side": order.side,
                "type": "STOP_MARKET",
                "quantity": self._fmt_decimal(order.quantity),
                "triggerPrice": self._fmt_decimal(order.stop_price),  # type: ignore[arg-type]
                "workingType": "CONTRACT_PRICE",
            }
            if order.client_order_id:
                params["clientAlgoId"] = order.client_order_id
            log.info("order_submit", extra={"event": "order_submit", "context": {"params": params}})
            return "algo", params

        if order.order_type == "STOP":
            # Stop-LIMIT conditional via Algo Order endpoint.
            params: dict[str, Any] = {
                "algoType": "CONDITIONAL",
                "symbol": order.symbol,
                "side": order.side,
                "type": "STOP",
                "quantity": self._fmt_decimal(order.quantity),
                "price": self._fmt_decimal(order.price),  # type: ignore[arg-type]
                "triggerPrice": self._fmt_decimal(order.stop_price),  # type: ignore[arg-type]
                "timeInForce": order.time_in_force,
                "workingType": "CONTRACT_PRICE",
            }
            if order.client_order_id:
                params["clientAlgoId"] = order.client_order_id
            log.info("order_submit", extra={"event": "order_submit", "context": {"params": params}})
            return "algo", params

        params2: dict[str, Any] = {
            "symbol": order.symbol,
            "side": order.side,
            "type": order.order_type,
            "quantity": self._fmt_decimal(order.quantity),
            "newOrderRespType": "RESULT",
        }
        if order.client_order_id:
            params2["newClientOrderId"] = order.client_order_id
        if order.order_type == "LIMIT":
            params2["price"] = self._fmt_decimal(order.price)  # type: ignore[arg-type]
            params2["timeInForce"] = order.time_in_force

        log.info("order_submit", extra={"event": "order_submit", "context": {"params": params2}})
        return "order", params2

    def place_order(self, order: OrderInput, *, recv_window: int | None = None) -> dict[str, Any]:
        endpoint, params = self.build_request(order)
        if endpoint == "algo":
            return self._client.new_algo_order_with_window(params=params, recv_window=recv_window)
        return self._client.new_order_with_window(params=params, recv_window=recv_window)
