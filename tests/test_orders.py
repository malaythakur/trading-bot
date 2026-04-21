from trading_bot.bot.client import BinanceFuturesClient
from trading_bot.bot.orders import OrderService
from trading_bot.bot.validators import OrderInput


class _FakeClient(BinanceFuturesClient):
    def __init__(self):
        super().__init__(api_key="k", api_secret="s", base_url="https://example.com")
        self.last_new_order_params = None
        self.last_new_algo_order_params = None

    def new_order_with_window(self, *, params, recv_window=None):
        self.last_new_order_params = dict(params)
        return {"orderId": 1, "status": "NEW", "executedQty": "0", "avgPrice": "0"}

    def new_algo_order_with_window(self, *, params, recv_window=None):
        self.last_new_algo_order_params = dict(params)
        return {"algoId": 2, "algoStatus": "NEW", "orderType": params.get("type")}


def test_market_routes_to_new_order():
    c = _FakeClient()
    svc = OrderService(c)
    o = OrderInput.parse(symbol="BTCUSDT", side="BUY", order_type="MARKET", quantity="0.001")
    resp = svc.place_order(o)
    assert resp["orderId"] == 1
    assert c.last_new_order_params["type"] == "MARKET"
    assert c.last_new_algo_order_params is None


def test_limit_routes_to_new_order_with_price():
    c = _FakeClient()
    svc = OrderService(c)
    o = OrderInput.parse(symbol="BTCUSDT", side="SELL", order_type="LIMIT", quantity="0.001", price="120000")
    svc.place_order(o)
    assert c.last_new_order_params["type"] == "LIMIT"
    assert c.last_new_order_params["price"] == "120000"
    assert c.last_new_order_params["timeInForce"] == "GTC"
    assert c.last_new_algo_order_params is None


def test_stop_market_routes_to_algo_order():
    c = _FakeClient()
    svc = OrderService(c)
    o = OrderInput.parse(
        symbol="BTCUSDT", side="BUY", order_type="STOP_MARKET", quantity="0.001", stop_price="119900"
    )
    resp = svc.place_order(o)
    assert resp["algoId"] == 2
    assert c.last_new_algo_order_params["algoType"] == "CONDITIONAL"
    assert c.last_new_algo_order_params["type"] == "STOP_MARKET"
    assert c.last_new_algo_order_params["triggerPrice"] == "119900"
    assert c.last_new_order_params is None


def test_stop_routes_to_algo_order_with_price_and_trigger():
    c = _FakeClient()
    svc = OrderService(c)
    o = OrderInput.parse(
        symbol="BTCUSDT",
        side="BUY",
        order_type="STOP",
        quantity="0.001",
        price="120000",
        stop_price="119900",
    )
    svc.place_order(o)
    assert c.last_new_algo_order_params["type"] == "STOP"
    assert c.last_new_algo_order_params["price"] == "120000"
    assert c.last_new_algo_order_params["triggerPrice"] == "119900"

