"""
ForexPipCalcBot - Telegram bot for pip value, position size and P/L calculations.

Deployment: Railway (via GitHub). Runs in polling mode so no public URL /
webhook setup is required - just set the TELEGRAM_BOT_TOKEN env var on Railway
and it works out of the box.
"""

import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

import calculator

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DEFAULT_ACCOUNT_CURRENCY = "USD"

HELP_TEXT = (
    "*ForexPipCalcBot*\n\n"
    "I calculate pip values, position sizes and profit/loss for forex trades.\n\n"
    "*Commands:*\n"
    "`/pip PAIR LOTSIZE [ACCOUNT_CCY]`\n"
    "  e.g. `/pip EURUSD 0.1` or `/pip USDJPY 1 EUR`\n\n"
    "`/lots PAIR BALANCE RISK% STOPLOSS_PIPS [ACCOUNT_CCY]`\n"
    "  e.g. `/lots GBPUSD 1000 2 30`\n\n"
    "`/pl PAIR LOTSIZE ENTRY EXIT buy|sell [ACCOUNT_CCY]`\n"
    "  e.g. `/pl EURUSD 0.5 1.0850 1.0900 buy`\n\n"
    "Account currency defaults to USD if not given."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def pip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: `/pip PAIR LOTSIZE [ACCOUNT_CCY]`\ne.g. `/pip EURUSD 0.1`",
            parse_mode="Markdown",
        )
        return
    try:
        pair = args[0]
        lot_size = float(args[1])
        account_ccy = args[2] if len(args) > 2 else DEFAULT_ACCOUNT_CURRENCY

        result = await calculator.pip_value(pair, lot_size, account_ccy)
        await update.message.reply_text(
            f"*{result['pair']}* — {result['lot_size']} lot(s)\n"
            f"Pip size: {result['pip_size']}\n"
            f"1 pip = *{result['pip_value']} {result['account_currency']}*",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ {e}")


async def lots_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Usage: `/lots PAIR BALANCE RISK% STOPLOSS_PIPS [ACCOUNT_CCY]`\n"
            "e.g. `/lots GBPUSD 1000 2 30`",
            parse_mode="Markdown",
        )
        return
    try:
        pair = args[0]
        balance = float(args[1])
        risk_pct = float(args[2])
        sl_pips = float(args[3])
        account_ccy = args[4] if len(args) > 4 else DEFAULT_ACCOUNT_CURRENCY

        result = await calculator.position_size(pair, account_ccy, balance, risk_pct, sl_pips)
        await update.message.reply_text(
            f"*{result['pair']}* — risking {risk_pct}% of {balance} {result['account_currency']}\n"
            f"Risk amount: {result['risk_amount']} {result['account_currency']}\n"
            f"Stop loss: {result['stop_loss_pips']} pips\n"
            f"Recommended size: *{result['recommended_lots']} lots* "
            f"({result['recommended_units']} units)",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ {e}")


async def pl_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 5:
        await update.message.reply_text(
            "Usage: `/pl PAIR LOTSIZE ENTRY EXIT buy|sell [ACCOUNT_CCY]`\n"
            "e.g. `/pl EURUSD 0.5 1.0850 1.0900 buy`",
            parse_mode="Markdown",
        )
        return
    try:
        pair = args[0]
        lot_size = float(args[1])
        entry = float(args[2])
        exit_ = float(args[3])
        direction = args[4]
        account_ccy = args[5] if len(args) > 5 else DEFAULT_ACCOUNT_CURRENCY

        result = await calculator.profit_loss(pair, lot_size, entry, exit_, direction, account_ccy)
        sign = "🟢 Profit" if result["profit_loss"] >= 0 else "🔴 Loss"
        await update.message.reply_text(
            f"*{result['pair']}* — {result['direction'].upper()} {result['lot_size']} lot(s)\n"
            f"Move: {result['pips']} pips\n"
            f"{sign}: *{result['profit_loss']} {result['account_currency']}*",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ {e}")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "I didn't recognize that command. Send /help to see what I can do."
    )


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Set it in Railway's Variables tab."
        )

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("pip", pip_command))
    application.add_handler(CommandHandler("lots", lots_command))
    application.add_handler(CommandHandler("pl", pl_command))

    logger.info("ForexPipCalcBot starting (polling mode)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
