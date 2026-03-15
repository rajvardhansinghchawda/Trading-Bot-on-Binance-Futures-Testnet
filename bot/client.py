"""
Low-level Binance Futures Testnet client.
Handles authentication (HMAC-SHA256), request signing, and HTTP transport.
All raw API interactions are isolated here so the rest of the app stays clean.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger("trading_bot.client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_TIMEOUT = 10  # seconds


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error payload."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceClient:
    """
    Thin wrapper around the Binance USDT-M Futures REST API (testnet).

    Args:
        api_key: Testnet API key.
        api_secret: Testnet API secret.
        base_url: Override the default testnet base URL (useful for mocking).
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("Both api_key and api_secret must be non-empty strings.")

        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        logger.debug("BinanceClient initialised — base_url=%s", self._base_url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Append a timestamp and HMAC-SHA256 signature to *params*."""
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request and return the parsed JSON response.

        Raises:
            BinanceAPIError: On non-2xx responses or Binance error payloads.
            requests.exceptions.RequestException: On network failures.
        """
        params = params or {}
        if signed:
            params = self._sign(params)

        url = f"{self._base_url}{path}"
        logger.debug("→ %s %s  params=%s", method.upper(), url, {k: v for k, v in params.items() if k != "signature"})

        try:
            response = self._session.request(
                method,
                url,
                params=params if method.upper() == "GET" else None,
                data=params if method.upper() != "GET" else None,
                timeout=self._timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network connection error: %s", exc)
            raise
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out after %ds: %s", self._timeout, exc)
            raise

        logger.debug("← HTTP %s  body=%s", response.status_code, response.text[:500])

        # Handle empty response body
        if not response.text.strip():
            if response.ok:
                return {}
            response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise

        # Binance wraps errors in {"code": <negative int>, "msg": "..."}
        if isinstance(data, dict) and data.get("code", 0) < 0:
            raise BinanceAPIError(data["code"], data.get("msg", "Unknown error"))

        if not response.ok:
            response.raise_for_status()

        return data

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_server_time(self) -> int:
        """Return Binance server time in milliseconds (connectivity check)."""
        data = self._request("GET", "/fapi/v1/time", signed=False)
        return data["serverTime"]

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Return exchange info, optionally filtered to a single symbol."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/exchangeInfo", params=params, signed=False)

    def get_account(self) -> Dict[str, Any]:
        """Return futures account details (balances, positions, etc.)."""
        return self._request("GET", "/fapi/v2/account")

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: Optional[str] = None,
        time_in_force: str = "GTC",
        stop_price: Optional[str] = None,
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Place a new order on USDT-M Futures.
        Routes conditional orders (containing 'STOP') to the algo endpoint.
        """
        if "STOP" in str(order_type).upper():
             return self.place_algo_order(
                 symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                time_in_force=time_in_force,
                reduce_only=reduce_only
            )

        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type == "LIMIT":
            if not price:
                raise ValueError("price is required for LIMIT orders.")
            params["price"] = price
            params["timeInForce"] = time_in_force

        if reduce_only:
            params["reduceOnly"] = "true"

        logger.info(
            "Placing order — symbol=%s side=%s type=%s qty=%s price=%s",
            symbol, side, order_type, quantity, price or "N/A",
        )
        return self._request("POST", "/fapi/v1/order", params=params)

    def place_algo_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: Optional[str] = None,
        stop_price: Optional[str] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Place a conditional order via the Algo endpoint.
        """
        if not stop_price:
            raise ValueError(f"stop_price (triggerPrice) is required for {order_type} orders.")

        # Map internal types to Algo types
        # STOP_MARKET -> STOP_MARKET
        # STOP_LIMIT -> STOP
        algo_type_str = "STOP_MARKET" if order_type.upper() == "STOP_MARKET" else "STOP"

        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "algoType": "CONDITIONAL",
            "type": algo_type_str,
            "quantity": quantity,
            "triggerPrice": stop_price,
        }

        if algo_type_str == "STOP":
            if not price:
                raise ValueError("price is required for STOP (stop-limit) orders.")
            params["price"] = price
            params["timeInForce"] = time_in_force

        if reduce_only:
            params["reduceOnly"] = "true"

        logger.info(
            "Placing ALGO order — symbol=%s side=%s type=%s qty=%s trigger=%s price=%s",
            symbol, side, order_type, quantity, stop_price, price or "N/A",
        )
        return self._request("POST", "/fapi/v1/algoOrder", params=params)

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Fetch details of an existing order."""
        return self._request("GET", "/fapi/v1/order", params={"symbol": symbol, "orderId": order_id})

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an open order."""
        return self._request("DELETE", "/fapi/v1/order", params={"symbol": symbol, "orderId": order_id})

    def get_positions(self) -> list[Dict[str, Any]]:
        """Return a list of open positions (non-zero size)."""
        data = self._request("GET", "/fapi/v2/positionRisk")
        # Ensure data is a list
        if not isinstance(data, list):
            logger.warning("Expected list from positionRisk, got %s", type(data))
            return []
        return [p for p in data if float(p.get("positionAmt", 0)) != 0]