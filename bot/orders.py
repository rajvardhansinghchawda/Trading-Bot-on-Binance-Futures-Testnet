"""
Order placement logic and result formatting.
Acts as a bridge between the CLI layer and the raw BinanceClient.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from .client import BinanceClient, BinanceAPIError

logger = logging.getLogger("trading_bot.orders")


class OrderResult:
    """Parsed and human-friendly representation of a Binance order response."""

    def __init__(self, raw: dict) -> None:
        self.raw = raw
        self.order_id: int = raw.get("orderId", raw.get("algoId", 0))
        self.client_order_id: str = raw.get("clientOrderId", "")
        self.symbol: str = raw.get("symbol", "")
        self.side: str = raw.get("side", "")
        self.order_type: str = raw.get("type", "")
        self.orig_qty: str = raw.get("origQty", raw.get("quantity", ""))
        self.executed_qty: str = raw.get("executedQty", "")
        self.avg_price: str = raw.get("avgPrice", "0")
        self.price: str = raw.get("price", "0")
        self.stop_price: str = raw.get("stopPrice", raw.get("triggerPrice", "0"))
        self.status: str = raw.get("status", "")
        self.time_in_force: str = raw.get("timeInForce", "")
        self.reduce_only: bool = raw.get("reduceOnly", False)
        self.update_time: int = raw.get("updateTime", 0)

    def is_filled(self) -> bool:
        return self.status == "FILLED"

    def summary_lines(self) -> list[str]:
        lines = [
            f"  Order ID      : {self.order_id}",
            f"  Symbol        : {self.symbol}",
            f"  Side          : {self.side}",
            f"  Type          : {self.order_type}",
            f"  Status        : {self.status}",
            f"  Orig Qty      : {self.orig_qty}",
            f"  Executed Qty  : {self.executed_qty}",
        ]
        if self.avg_price and self.avg_price != "0":
            lines.append(f"  Avg Price     : {self.avg_price}")
        if self.price and self.price != "0":
            lines.append(f"  Limit Price   : {self.price}")
        if self.stop_price and self.stop_price != "0":
            lines.append(f"  Stop Price    : {self.stop_price}")
        if self.time_in_force:
            lines.append(f"  Time-in-Force : {self.time_in_force}")
        return lines


def place_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    reduce_only: bool = False,
) -> OrderResult:
    """Place a MARKET order and return an OrderResult."""
    logger.info("Market order — %s %s qty=%s", side, symbol, quantity)
    raw = client.place_order(
        symbol=symbol,
        side=side,
        order_type="MARKET",
        quantity=str(quantity),
        reduce_only=reduce_only,
    )
    result = OrderResult(raw)
    logger.info("Market order placed — orderId=%s status=%s execQty=%s avgPrice=%s",
                result.order_id, result.status, result.executed_qty, result.avg_price)
    return result


def place_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
) -> OrderResult:
    """Place a LIMIT order and return an OrderResult."""
    logger.info("Limit order — %s %s qty=%s price=%s tif=%s", side, symbol, quantity, price, time_in_force)
    raw = client.place_order(
        symbol=symbol,
        side=side,
        order_type="LIMIT",
        quantity=str(quantity),
        price=str(price),
        time_in_force=time_in_force,
        reduce_only=reduce_only,
    )
    result = OrderResult(raw)
    logger.info("Limit order placed — orderId=%s status=%s price=%s qty=%s",
                result.order_id, result.status, result.price, result.orig_qty)
    return result


def place_stop_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    stop_price: Decimal,
    reduce_only: bool = False,
) -> OrderResult:
    """Place a STOP_MARKET order and return an OrderResult."""
    logger.info("Stop-market order — %s %s qty=%s stopPrice=%s", side, symbol, quantity, stop_price)
    raw = client.place_order(
        symbol=symbol,
        side=side,
        order_type="STOP_MARKET",
        quantity=str(quantity),
        stop_price=str(stop_price),
        reduce_only=reduce_only,
    )
    result = OrderResult(raw)
    logger.info("Stop-market order placed — orderId=%s status=%s stopPrice=%s",
                result.order_id, result.status, result.stop_price)
    return result


def place_stop_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    stop_price: Decimal,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
) -> OrderResult:
    """Place a STOP_LIMIT order and return an OrderResult."""
    logger.info("Stop-limit order — %s %s qty=%s price=%s stopPrice=%s tif=%s", 
                side, symbol, quantity, price, stop_price, time_in_force)
    raw = client.place_order(
        symbol=symbol,
        side=side,
        order_type="STOP_LIMIT",
        quantity=str(quantity),
        price=str(price),
        stop_price=str(stop_price),
        time_in_force=time_in_force,
        reduce_only=reduce_only,
    )
    result = OrderResult(raw)
    logger.info("Stop-limit order placed — orderId=%s status=%s stopPrice=%s price=%s",
                result.order_id, result.status, result.stop_price, result.price)
    return result


def dispatch_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: Decimal,
    price: Optional[Decimal] = None,
    stop_price: Optional[Decimal] = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
) -> OrderResult:
    """
    Route an order to the correct placement function based on order_type.
    Raises ValueError for unrecognised order types.
    """
    order_type = order_type.upper()
    if order_type == "MARKET":
        return place_market_order(client, symbol, side, quantity, reduce_only)
    elif order_type == "LIMIT":
        if price is None:
            raise ValueError("price is required for LIMIT orders.")
        return place_limit_order(client, symbol, side, quantity, price, time_in_force, reduce_only)
    elif order_type == "STOP_MARKET":
        if stop_price is None:
            raise ValueError("stop_price is required for STOP_MARKET orders.")
        return place_stop_market_order(client, symbol, side, quantity, stop_price, reduce_only)
    elif order_type == "STOP_LIMIT":
        if price is None:
            raise ValueError("price is required for STOP_LIMIT orders.")
        if stop_price is None:
            raise ValueError("stop_price is required for STOP_LIMIT orders.")
        return place_stop_limit_order(client, symbol, side, quantity, price, stop_price, time_in_force, reduce_only)
    else:
        raise ValueError(f"Unsupported order type: {order_type}")
