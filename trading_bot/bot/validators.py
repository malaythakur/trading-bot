from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from .errors import ValidationError

Side = Literal["BUY", "SELL"]
# Native /fapi/v1/order types supported on USDT-M Futures.
# Note: Some environments reject "STOP" (stop-limit) and require algo endpoints.
OrderType = Literal["MARKET", "LIMIT", "STOP_MARKET", "STOP"]


def _to_decimal(value: Any, *, field_name: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise ValidationError(f"Invalid numeric value for {field_name}: {value}") from e
    return d


@dataclass(frozen=True)
class OrderInput:
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: Literal["GTC"] = "GTC"
    client_order_id: str | None = None

    @classmethod
    def parse(
        cls,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Any,
        price: Any = None,
        stop_price: Any = None,
        time_in_force: str = "GTC",
        client_order_id: str | None = None,
    ) -> "OrderInput":
        sym = (symbol or "").strip().upper()
        if not (3 <= len(sym) <= 25):
            raise ValidationError("symbol must be 3..25 characters")

        s = (side or "").strip().upper()
        if s not in ("BUY", "SELL"):
            raise ValidationError("side must be BUY or SELL")

        ot = (order_type or "").strip().upper()
        if ot not in ("MARKET", "LIMIT", "STOP_MARKET", "STOP"):
            raise ValidationError("type must be MARKET, LIMIT, STOP_MARKET, or STOP")

        tif = (time_in_force or "").strip().upper()
        if tif != "GTC":
            raise ValidationError("time_in_force must be GTC")

        qty = _to_decimal(quantity, field_name="quantity")
        if qty <= 0:
            raise ValidationError("quantity must be > 0")

        px = None if price is None else _to_decimal(price, field_name="price")
        spx = None if stop_price is None else _to_decimal(stop_price, field_name="stop_price")
        if px is not None and px <= 0:
            raise ValidationError("price must be > 0")
        if spx is not None and spx <= 0:
            raise ValidationError("stop_price must be > 0")

        if ot == "LIMIT" and px is None:
            raise ValidationError("price is required for LIMIT orders")
        if ot == "MARKET" and px is not None:
            raise ValidationError("price must not be provided for MARKET orders")
        if ot == "STOP_MARKET":
            if spx is None:
                raise ValidationError("STOP_MARKET orders require stop_price")
            if px is not None:
                raise ValidationError("price must not be provided for STOP_MARKET")
        if ot == "STOP":
            if spx is None or px is None:
                raise ValidationError("STOP orders require both price and stop_price")

        return cls(
            symbol=sym,
            side=s,  # type: ignore[arg-type]
            order_type=ot,  # type: ignore[arg-type]
            quantity=qty,
            price=px,
            stop_price=spx,
            time_in_force="GTC",
            client_order_id=(client_order_id.strip() if client_order_id else None),
        )

    def to_public_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # match CLI naming the task spec uses
        d["type"] = d.pop("order_type")
        d["stop_price"] = d.get("stop_price")
        return d
