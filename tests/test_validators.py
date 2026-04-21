import pytest

from trading_bot.bot.errors import ValidationError
from trading_bot.bot.validators import OrderInput


def test_market_requires_no_price():
    o = OrderInput.parse(symbol="btcusdt", side="buy", order_type="MARKET", quantity="0.001")
    assert o.symbol == "BTCUSDT"
    assert o.price is None

    with pytest.raises(ValidationError):
        OrderInput.parse(symbol="BTCUSDT", side="BUY", order_type="MARKET", quantity="0.1", price="1")


def test_limit_requires_price():
    with pytest.raises(ValidationError):
        OrderInput.parse(symbol="BTCUSDT", side="BUY", order_type="LIMIT", quantity="0.1")

    o = OrderInput.parse(symbol="BTCUSDT", side="SELL", order_type="LIMIT", quantity="0.1", price="120000")
    assert str(o.price) == "120000"


def test_stop_market_requires_stop_price_and_no_price():
    with pytest.raises(ValidationError):
        OrderInput.parse(symbol="BTCUSDT", side="BUY", order_type="STOP_MARKET", quantity="0.1")

    with pytest.raises(ValidationError):
        OrderInput.parse(
            symbol="BTCUSDT",
            side="BUY",
            order_type="STOP_MARKET",
            quantity="0.1",
            stop_price="100",
            price="101",
        )

    o = OrderInput.parse(
        symbol="BTCUSDT", side="BUY", order_type="STOP_MARKET", quantity="0.1", stop_price="100"
    )
    assert str(o.stop_price) == "100"
    assert o.price is None


def test_stop_requires_price_and_stop_price():
    with pytest.raises(ValidationError):
        OrderInput.parse(symbol="BTCUSDT", side="BUY", order_type="STOP", quantity="0.1", stop_price="100")

    with pytest.raises(ValidationError):
        OrderInput.parse(symbol="BTCUSDT", side="BUY", order_type="STOP", quantity="0.1", price="101")

    o = OrderInput.parse(
        symbol="BTCUSDT", side="BUY", order_type="STOP", quantity="0.1", price="101", stop_price="100"
    )
    assert str(o.price) == "101"
    assert str(o.stop_price) == "100"


def test_side_validation():
    with pytest.raises(ValidationError):
        OrderInput.parse(symbol="BTCUSDT", side="HOLD", order_type="MARKET", quantity="0.1")


def test_quantity_validation():
    with pytest.raises(ValidationError):
        OrderInput.parse(symbol="BTCUSDT", side="BUY", order_type="MARKET", quantity="0")

    with pytest.raises(ValidationError):
        OrderInput.parse(symbol="BTCUSDT", side="BUY", order_type="MARKET", quantity="-1")

