#!/usr/bin/env python3

"""
cli.py — Trading Bot CLI entry point
=====================================
Usage examples:

  # Market BUY
  python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.001

  # Limit SELL
  python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --qty 0.001 --price 70000

  # Stop-Market BUY (bonus order type)
  python cli.py place --symbol ETHUSDT --side BUY --type STOP_MARKET --qty 0.01 --stop-price 2600

  # Check server connectivity
  python cli.py ping

  # Show account balances
  python cli.py account
"""

from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()
import argparse
import os
import sys
from decimal import Decimal

from bot.client import BinanceAPIError, BinanceClient
from bot.logging_config import setup_logging
from bot.orders import dispatch_order
from bot.validators import validate_all

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BANNER = """
╔══════════════════════════════════════════════════╗
║      Binance Futures Testnet — Trading Bot       ║
╚══════════════════════════════════════════════════╝
"""


def _get_client(args: argparse.Namespace) -> BinanceClient:
    """Build a BinanceClient from CLI flags or environment variables."""
    api_key = getattr(args, "api_key", None) or os.environ.get("BINANCE_API_KEY", "")
    api_secret = getattr(args, "api_secret", None) or os.environ.get("BINANCE_API_SECRET", "")

    if not api_key or not api_secret:
        print(
            "ERROR: API credentials not found.\n"
            "  Pass --api-key / --api-secret or set environment variables:\n"
            "    export BINANCE_API_KEY=<your_key>\n"
            "    export BINANCE_API_SECRET=<your_secret>",
            file=sys.stderr,
        )
        sys.exit(1)

    return BinanceClient(api_key=api_key, api_secret=api_secret)


def _print_order_request(params: dict) -> None:
    print("\n── Order Request ──────────────────────────────")
    print(f"  Symbol     : {params['symbol']}")
    print(f"  Side       : {params['side']}")
    print(f"  Type       : {params['order_type']}")
    print(f"  Quantity   : {params['quantity']}")
    if params.get("price"):
        print(f"  Price      : {params['price']}")
    if params.get("stop_price"):
        print(f"  Stop Price : {params['stop_price']}")
    print("───────────────────────────────────────────────")


def _print_order_result(result) -> None:
    print("\n── Order Response ─────────────────────────────")
    for line in result.summary_lines():
        print(line)
    print("───────────────────────────────────────────────")


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------

def cmd_ping(args: argparse.Namespace, logger) -> int:
    """Check connectivity to Binance Futures Testnet."""
    client = _get_client(args)
    try:
        server_time = client.get_server_time()
        print(f"✓ Connected to Binance Futures Testnet  (server time: {server_time} ms)")
        logger.info("Ping successful — server_time=%s", server_time)
        return 0
    except Exception as exc:
        print(f"✗ Connection failed: {exc}", file=sys.stderr)
        logger.error("Ping failed: %s", exc)
        return 1


def cmd_account(args: argparse.Namespace, logger) -> int:
    """Display USDT futures account balances and open positions."""
    client = _get_client(args)
    try:
        # Balances
        account = client.get_account()
        assets = [a for a in account.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
        print("\n── Account Balances ───────────────────────────")
        if not assets:
            print("  (no non-zero balances)")
        for asset in assets:
            print(
                f"  {asset['asset']:<8}  wallet={asset['walletBalance']:<18} "
                f"unrealizedPnL={asset['unrealizedProfit']}"
            )
        
        # Positions
        positions = client.get_positions()
        print("\n── Open Positions ─────────────────────────────")
        if not positions:
            print("  (no open positions)")
        for pos in positions:
            side = "LONG" if float(pos['positionAmt']) > 0 else "SHORT"
            print(
                f"  {pos['symbol']:<10} {side:<6} size={pos['positionAmt']:<10} "
                f"entry={pos['entryPrice']:<10} pnl={pos['unRealizedProfit']}"
            )
        print("───────────────────────────────────────────────")
        
        logger.info("Account info fetched — %d asset(s), %d position(s)", len(assets), len(positions))
        return 0
    except BinanceAPIError as exc:
        print(f"✗ API error {exc.code}: {exc.message}", file=sys.stderr)
        logger.error("Account fetch failed — %s", exc)
        return 1
    except Exception as exc:
        print(f"✗ Unexpected error: {exc}", file=sys.stderr)
        logger.exception("Account fetch raised exception")
        return 1


def cmd_place(args: argparse.Namespace, logger) -> int:
    """Validate inputs, place an order, and print the result."""
    # ---- validate inputs -----------------------------------------------
    try:
        params = validate_all(
            symbol=args.symbol,
            side=args.side,
            order_type=args.type,
            quantity=args.quantity,
            price=args.price,
        )
        # handle stop_price separately (not in validate_all signature)
        stop_price: Decimal | None = None
        if args.type.upper() in ("STOP_MARKET", "STOP_LIMIT"):
            from bot.validators import validate_stop_price as _vsp
            stop_price = _vsp(args.stop_price, args.type.upper())

    except ValueError as exc:
        print(f"✗ Validation error: {exc}", file=sys.stderr)
        logger.warning("Validation failed: %s", exc)
        return 1

    params["stop_price"] = stop_price
    _print_order_request(params)

    # ---- place order ----------------------------------------------------
    client = _get_client(args)
    try:
        result = dispatch_order(
            client=client,
            symbol=params["symbol"],
            side=params["side"],
            order_type=params["order_type"],
            quantity=params["quantity"],
            price=params.get("price"),
            stop_price=params.get("stop_price"),
            time_in_force=getattr(args, "tif", "GTC") or "GTC",
            reduce_only=getattr(args, "reduce_only", False),
        )
    except BinanceAPIError as exc:
        print(f"\n✗ Order FAILED — API error {exc.code}: {exc.message}", file=sys.stderr)
        logger.error("Order placement API error — code=%s msg=%s", exc.code, exc.message)
        return 1
    except ValueError as exc:
        print(f"\n✗ Order FAILED — {exc}", file=sys.stderr)
        logger.error("Order placement value error — %s", exc)
        return 1
    except Exception as exc:
        print(f"\n✗ Order FAILED — unexpected error: {exc}", file=sys.stderr)
        logger.exception("Order placement raised unexpected exception")
        return 1

    _print_order_result(result)
    status_icon = "✓" if result.status in ("FILLED", "NEW", "PARTIALLY_FILLED") else "⚠"
    print(f"\n{status_icon} Order submitted successfully!\n")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot",
    )
    # Credentials / Global Config
    parser.add_argument("--api-key", dest="api_key", metavar="KEY", help="Binance API key (or set BINANCE_API_KEY env var)")
    parser.add_argument("--api-secret", dest="api_secret", metavar="SECRET", help="Binance API secret (or set BINANCE_API_SECRET env var)")
    parser.add_argument("--log-level", dest="log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Console log level (default: INFO)")
    parser.add_argument("--log-dir", dest="log_dir", default="logs", help="Directory for log files (default: logs/)")

    # Order Parameters (Top-level)
    parser.add_argument("--symbol", help="Trading pair (e.g. BTCUSDT)")
    parser.add_argument("--side", choices=["BUY", "SELL"], help="Order side")
    parser.add_argument("--type", choices=["MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT"], dest="type", help="Order type")
    parser.add_argument("--quantity", "--qty", dest="quantity", help="Order quantity")
    parser.add_argument("--price", default=None, help="Limit price (required for LIMIT)")
    parser.add_argument("--stop-price", "--stop", dest="stop_price", default=None, help="Stop trigger price (required for STOP_MARKET)")
    parser.add_argument("--tif", default="GTC", choices=["GTC", "IOC", "FOK"], help="Time-in-force for LIMIT orders (default: GTC)")
    parser.add_argument("--reduce-only", dest="reduce_only", action="store_true", help="Reduce-only flag")

    # Utilities
    parser.add_argument("--ping", action="store_true", help="Check connectivity to testnet")
    parser.add_argument("--account", action="store_true", help="Show account balances")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(BANNER)
    parser = build_parser()
    args = parser.parse_args()

    logger = setup_logging(log_dir=args.log_dir, log_level=args.log_level)
    logger.debug("CLI args: %s", vars(args))

    if args.ping:
        sys.exit(cmd_ping(args, logger))
    if args.account:
        sys.exit(cmd_account(args, logger))

    # Default behaviour: place an order if symbol/side/type/quantity are provided
    if all([args.symbol, args.side, args.type, args.quantity]):
        # Map args.quantity back to what cmd_place expects (it was using args.qty)
        # Actually I will just update cmd_place to use args.quantity
        sys.exit(cmd_place(args, logger))
    
    # If no specific action matched, show help
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
