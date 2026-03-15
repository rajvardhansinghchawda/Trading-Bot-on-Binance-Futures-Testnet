# Binance Futures Testnet — Trading Bot

A high-performance, production-quality Python CLI application for the Binance USDT-M Futures Testnet. Built with clean architecture, robust error handling, and structured logging.

---

## 🚀 Key Features

- **Standard Order Types**: MARKET and LIMIT orders.
- **Advanced Conditional Orders**: STOP_MARKET and STOP_LIMIT (Implemented via the dedicated **Binance Algo Order API**).
- **Position Tracking**: Real-time position monitoring including entry price and PnL.
- **Production Logging**: Structured JSON-like logs in `logs/trading_bot.log` capturing every API interaction.
- **Environment Support**: Securely manage API keys via `.env` files.

---

## 📂 Project Structure

```
trading_bot/
├── bot/
│   ├── client.py          # Algo-aware Binance REST client
│   ├── orders.py          # Logic for dispatching and formatting orders
│   ├── validators.py      # Strict input validation
│   └── logging_config.py # Centralized logging system
├── cli.py                 # Feature-rich CLI entry point
├── logs/                  # Application logs
├── .env.example           # Configuration template
├── .gitignore             # Standard git exclusions
├── requirements.txt       # Project dependencies
└── README.md
```

---

## 🛠 Setup

### 1. Prerequisites
- Python 3.8+
- [Binance Futures Testnet](https://testnet.binancefuture.com) account

### 2. Configuration
Copy the template and add your API keys:
```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Install
```bash
pip install -r requirements.txt
```

---

## 🕹 Usage

### Connectivity Check
```bash
python cli.py --ping
```

### Account & Positions
```bash
python cli.py --account
```

### Place Orders
The bot uses a flat flag structure for efficiency.

**Market Order:**
```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --qty 0.002
```

**Limit Order:**
```bash
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --qty 0.002 --price 85000
```

**Stop-Market:**
```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.002 --stop 65000
```

**Stop-Limit:**
```bash
python cli.py --symbol BTCUSDT --side BUY --type STOP_LIMIT --qty 0.002 --stop 75000 --price 76000
```

> [!IMPORTANT]
> **Min Notional**: On Binance Futures Testnet, ensure `Quantity × Price` is at least **$100** to avoid filters.

---

## 📊 Logging & Debugging

All API traffic is captured in `logs/trading_bot.log`. 

- **Full Transparency**: Both request parameters and raw response bodies are logged.
- **Console Feedback**: High-level status updates are printed to the console. Use `--log-level DEBUG` for extra verbosity.

---

## 📜 Assumptions & Rules
1. **USDT-M**: Designed specifically for USDT-Margined Futures.
2. **One-Way Mode**: Operates in One-Way position mode (default).
3. **Safety First**: Implements `reduceOnly` support and strict local validation.
4. **No Dependencies**: All API signing logic is custom-built; no heavy third-party SDKs required.
