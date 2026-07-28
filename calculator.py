"""
Core forex calculation logic for ForexPipCalcBot.

Handles:
- Pip value calculation (per lot, in account currency)
- Position size / lot size calculation from risk %
- Profit / loss calculation between entry and exit price
- Live exchange rate lookups (for cross-currency conversion) via
  the free exchangerate.host API (no API key required).
"""

import re
import httpx

STANDARD_LOT_UNITS = 100_000
JPY_QUOTE = "JPY"


def normalize_pair(pair: str) -> str:
    """Turn 'eur/usd', 'EUR-USD', 'eurusd' etc into 'EURUSD'."""
    cleaned = re.sub(r"[^A-Za-z]", "", pair).upper()
    if len(cleaned) != 6:
        raise ValueError(
            f"'{pair}' doesn't look like a currency pair. Use format like EURUSD."
        )
    return cleaned


def split_pair(pair: str):
    pair = normalize_pair(pair)
    return pair[:3], pair[3:]


def pip_size_for(pair: str) -> float:
    _, quote = split_pair(pair)
    return 0.01 if quote == JPY_QUOTE else 0.0001


async def get_fx_rate(base: str, quote: str) -> float:
    """
    Return how many units of `quote` currency 1 unit of `base` currency buys.
    Uses exchangerate.host (free, keyless). Raises on failure.
    """
    if base == quote:
        return 1.0
    url = "https://api.exchangerate.host/latest"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params={"base": base, "symbols": quote})
        resp.raise_for_status()
        data = resp.json()
        rate = data.get("rates", {}).get(quote)
        if rate is None:
            raise ValueError(f"Could not fetch exchange rate for {base}/{quote}")
        return float(rate)


async def pip_value(pair: str, lot_size: float, account_currency: str = "USD") -> dict:
    """
    Calculate the value of 1 pip for a given pair and lot size,
    expressed in account_currency.
    """
    base, quote = split_pair(pair)
    account_currency = account_currency.upper()
    pip = pip_size_for(pair)
    units = lot_size * STANDARD_LOT_UNITS

    pip_value_in_quote = pip * units

    if quote == account_currency:
        value_in_account_ccy = pip_value_in_quote
    else:
        rate = await get_fx_rate(quote, account_currency)
        value_in_account_ccy = pip_value_in_quote * rate

    return {
        "pair": f"{base}/{quote}",
        "pip_size": pip,
        "lot_size": lot_size,
        "units": units,
        "account_currency": account_currency,
        "pip_value": round(value_in_account_ccy, 4),
    }


async def position_size(
    pair: str,
    account_currency: str,
    account_balance: float,
    risk_percent: float,
    stop_loss_pips: float,
) -> dict:
    """
    Calculate recommended lot size given account balance, risk % and stop-loss in pips.
    """
    if stop_loss_pips <= 0:
        raise ValueError("Stop loss (in pips) must be greater than 0.")

    risk_amount = account_balance * (risk_percent / 100)

    one_lot = await pip_value(pair, 1.0, account_currency)
    pip_val_per_lot = one_lot["pip_value"]

    if pip_val_per_lot <= 0:
        raise ValueError("Could not determine a valid pip value for this pair.")

    lots = risk_amount / (stop_loss_pips * pip_val_per_lot)

    return {
        "pair": one_lot["pair"],
        "account_currency": account_currency.upper(),
        "risk_amount": round(risk_amount, 2),
        "stop_loss_pips": stop_loss_pips,
        "recommended_lots": round(lots, 2),
        "recommended_units": round(lots * STANDARD_LOT_UNITS),
    }


async def profit_loss(
    pair: str,
    lot_size: float,
    entry_price: float,
    exit_price: float,
    direction: str,
    account_currency: str = "USD",
) -> dict:
    """
    Calculate profit/loss in account currency between entry and exit price.
    direction: 'buy' or 'sell'
    """
    direction = direction.lower()
    if direction not in ("buy", "sell"):
        raise ValueError("Direction must be 'buy' or 'sell'.")

    pip = pip_size_for(pair)
    price_diff = (exit_price - entry_price) if direction == "buy" else (entry_price - exit_price)
    pips = price_diff / pip

    pv = await pip_value(pair, lot_size, account_currency)
    result = pips * pv["pip_value"]

    return {
        "pair": pv["pair"],
        "direction": direction,
        "lot_size": lot_size,
        "pips": round(pips, 1),
        "account_currency": account_currency.upper(),
        "profit_loss": round(result, 2),
    }
