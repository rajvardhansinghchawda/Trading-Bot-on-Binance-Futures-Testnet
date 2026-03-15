# Binance Futures Testnet — Trading Bot

A clean, structured Python CLI application for placing orders on the Binance USDT-M Futures Testnet.

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package marker
│   ├── client.py            # Low-level Binance REST API client (auth, signing, HTTP)
│   ├── orders.py            # Order placement logic and result formatting
│   ├── validators.py        # Input validation helpers
│   └── logging_config.py   # Structured logging setup (file + console)
├── cli.py                   # CLI entry point (argparse)
├── logs/
│   ├── market_order_sample.log
│   └── limit_order_sample.log
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Prerequisites

- Python 3.8 or higher
- A Binance Futures Testnet account

### 2. Get Testnet Credentials

1. Visit [testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in (GitHub OAuth) → **API Key** section
3. Generate a new API key/secret pair
4. Copy both values somewhere safe — the secret is shown only once

### 3. Install Dependencies

```bash
cd trading_bot
pip install -r requirements.txt
```

### 4. Set Credentials

**Option A — environment variables (recommended)**
```bash
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"
```

**Option B — CLI flags (every command)**
```bash
python cli.py --api-key YOUR_KEY --api-secret YOUR_SECRET <command> ...
```

---

## How to Run

### Check connectivity
```bash
python cli.py ping
```
```
╔══════════════════════════════════════════════════╗
║      Binance Futures Testnet — Trading Bot       ║
╚══════════════════════════════════════════════════╝

✓ Connected to Binance Futures Testnet  (server time: 1741942800000 ms)
```

### Show account balances
```bash
python cli.py account
```

### Place a MARKET BUY order
```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

**Output:**
```
── Order Request ──────────────────────────────
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.001
───────────────────────────────────────────────

── Order Response ─────────────────────────────
  Order ID      : 4528813
  Symbol        : BTCUSDT
  Side          : BUY
  Type          : MARKET
  Status        : FILLED
  Orig Qty      : 0.001
  Executed Qty  : 0.001
  Avg Price     : 83241.50000
───────────────────────────────────────────────

✓ Order submitted successfully!
```

### Place a LIMIT SELL order
```bash
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 85000
```

### Place a STOP_MARKET order (bonus order type)
```bash
python cli.py --symbol ETHUSDT --side BUY --type STOP_MARKET --quantity 0.01 --stop-price 2600
```

### Extra flags
| Flag | Description | Default |
|---|---|---|
| `--tif` | Time-in-force for LIMIT orders (`GTC`, `IOC`, `FOK`) | `GTC` |
| `--reduce-only` | Mark order as reduce-only | off |
| `--log-level` | Console verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `--log-dir` | Directory for log files | `logs/` |

---

## Logging

Every run appends to `logs/trading_bot.log`.

- **File** — always captures `DEBUG` and above (full API request/response bodies)
- **Console** — shows `INFO` and above by default; use `--log-level DEBUG` for raw HTTP details

Sample entries from `logs/`:
- `market_order_sample.log` — MARKET BUY on BTCUSDT
- `limit_order_sample.log`  — LIMIT SELL on BTCUSDT

---

## Error Handling

The bot handles three categories of errors gracefully:

| Error Type | Example | Behaviour |
|---|---|---|
| Validation error | Negative quantity | Prints message, exits with code 1, no API call made |
| Binance API error | Invalid symbol, insufficient margin | Prints `code + message` from Binance, logs full detail |
| Network error | Timeout, DNS failure | Prints error, logs stack trace |

---

## Assumptions

1. **USDT-M Futures only** — The bot targets `/fapi/v1` endpoints (USDT-M). Coin-M futures (`/dapi`) are not supported.
2. **One-way position mode** — The default `positionSide=BOTH` is used. If your account is in Hedge Mode, orders may be rejected by the exchange.
3. **Quantity precision** — The user is responsible for providing quantities that match the symbol's step size. The bot passes values as-is; invalid precision will return a Binance API error.
4. **Credentials security** — API keys are read from environment variables or CLI flags. They are never written to disk or log files.
5. **Python ≥ 3.8** required for `from __future__ import annotations`.

---

## Dependencies

```
requests>=2.31.0
```

No third-party Binance SDK is used — all API interactions are plain HTTPS calls signed with HMAC-SHA256, keeping the dependency footprint minimal.
