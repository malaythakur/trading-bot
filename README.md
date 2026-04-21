# Trading Bot – Binance Futures Testnet (USDT‑M)

Small Python CLI app that places **MARKET** and **LIMIT** orders on **Binance Futures Testnet** with a clean separation between:
- **API client layer** (`trading_bot/bot/client.py`)
- **Order service** (`trading_bot/bot/orders.py`)
- **Validation** (`trading_bot/bot/validators.py`)
- **CLI entrypoint** (`trading_bot/cli.py`)
- **Structured logging** (`trading_bot/bot/logging_config.py`)

Bonus implemented: **STOP_MARKET (Stop‑Market)** and **STOP (Stop‑Limit)** order types (via Futures Algo Order endpoint).

## Setup

### 1) Create venv (recommended)

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2) Install deps

```bash
pip install -r requirements.txt
```

### 3) Configure credentials (do not hardcode)

Set environment variables:
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- optional: `BINANCE_FUTURES_BASE_URL` (defaults to `https://testnet.binancefuture.com`)

PowerShell example:

```powershell
$env:BINANCE_API_KEY="..."
$env:BINANCE_API_SECRET="..."
```

Or create a `.env` file in the repo root:

```env
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
BINANCE_FUTURES_BASE_URL=https://testnet.binancefuture.com
```

## Usage

### Health check

```bash
python -m trading_bot.cli health --log-file logs/health.log
```

### MARKET order (example)

```bash
python -m trading_bot.cli order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --log-file logs/market_order.log
```

### LIMIT order (example)

```bash
python -m trading_bot.cli order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 120000 --log-file logs/limit_order.log
```

### Run tests

```bash
python -m pytest -q
```

### Optional pro flags (additive)

- `--dry-run`: validate/build request without sending
- `--output json`: machine-readable stdout (for piping)
- `--client-order-id <id>`: idempotency key (`newClientOrderId` / `clientAlgoId`)
- `--use-server-time`: sync timestamp with Binance server clock
- `--recv-window <ms>`: pass `recvWindow` to signed endpoints

### STOP_MARKET (Stop‑Market) order (bonus)

```bash
python -m trading_bot.cli order \
  --symbol BTCUSDT \
  --side BUY \
  --type STOP_MARKET \
  --quantity 0.001 \
  --stop-price 119900 \
  --log-file logs/stop_order.log
```

### STOP (Stop‑Limit) order (bonus)

```bash
python -m trading_bot.cli order \
  --symbol BTCUSDT \
  --side BUY \
  --type STOP \
  --quantity 0.001 \
  --price 120000 \
  --stop-price 119900 \
  --log-file logs/stop_limit_order.log
```

## Output

The CLI prints:
- order request summary
- order response (including `orderId`, `status`, `executedQty`, `avgPrice` if present)
- success/failure message

Logs are written in JSON lines format for easy parsing/grep and include request/response metadata.

## Assumptions / Notes

- Uses Binance Futures REST endpoints under `/fapi/*`.
- Orders are sent with `newOrderRespType=RESULT` to return execution fields when available.
- This bot focuses on order placement; it does not manage leverage/margin settings.
