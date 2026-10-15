import json
import os
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TOKEN = os.environ["BOT_TOKEN"]  # set as env var or GitHub Secret, never hard-code
DATA = json.loads((Path(__file__).parent / "data" / "content.json").read_text(encoding="utf-8"))

TOPICS = DATA["topics"]
CREDIT = DATA["credit"]
CONTACT = DATA["contact"]
WELCOME = DATA["welcome"]
MENU_TITLE = DATA["menu_title"]

PER_PAGE = 6        # topics per menu page
MAX_PART = 3500     # characters per "part" (Telegram limit is 4096)


def split_parts(text: str) -> list[str]:
    """Split a long topic into readable parts, breaking on line boundaries."""
    parts, current = [], ""
    for line in text.split("\n"):
        if current and len(current) + len(line) + 1 > MAX_PART:
            parts.append(current.strip())
            current = ""
        current += line + "\n"
    if current.strip():
        parts.append(current.strip())
    return parts


for topic in TOPICS:
    topic["_parts"] = split_parts(topic["text"])


def menu_markup(page: int) -> InlineKeyboardMarkup:
    start = page * PER_PAGE
    chunk = TOPICS[start:start + PER_PAGE]
    rows = [
        [InlineKeyboardButton(t["title"], callback_data=f"t:{start + i}:0")]
        for i, t in enumerate(chunk)
    ]
    last_page = (len(TOPICS) - 1) // PER_PAGE
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"m:{page - 1}"))
    if page < last_page:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"m:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([
        InlineKeyboardButton("📞 Contact", callback_data="contact"),
        InlineKeyboardButton("ℹ️ Credit", callback_data="credit"),
    ])
    return InlineKeyboardMarkup(rows)


def part_view(ti: int, pi: int) -> tuple[str, InlineKeyboardMarkup]:
    topic = TOPICS[ti]
    parts = topic["_parts"]
    text = f"{topic['title']}  (part {pi + 1}/{len(parts)})\n\n{parts[pi]}"

    nav = []
    if pi > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev part", callback_data=f"t:{ti}:{pi - 1}"))
    if pi < len(parts) - 1:
        nav.append(InlineKeyboardButton("Next part ➡️", callback_data=f"t:{ti}:{pi + 1}"))
    rows = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("📚 Back to menu", callback_data=f"m:{ti // PER_PAGE}")])
    return text, InlineKeyboardMarkup(rows)


def back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("📚 Back to menu", callback_data="m:0")]])


def credit_text() -> str:
    return (
        f"{CREDIT['line1']}\n"
        f"{CREDIT['line2']}\n"
        f"{CREDIT['line3']}\n\n"
        f"TEL: {CREDIT['tel']}"
    )


def contact_text() -> str:
    return (
        f"{CONTACT['title']}\n\n"
        f"TEL: {CONTACT['tel']}\n"
        f"{CONTACT['note']}"
    )


async def safe_edit(query, text: str, markup: InlineKeyboardMarkup) -> None:
    try:
        await query.edit_message_text(text, reply_markup=markup)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"{WELCOME}\n\n{MENU_TITLE}", reply_markup=menu_markup(0))


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    fields = query.data.split(":")
    kind = fields[0]

    if kind == "m":
        await safe_edit(query, MENU_TITLE, menu_markup(int(fields[1])))
    elif kind == "t":
        text, markup = part_view(int(fields[1]), int(fields[2]))
        await safe_edit(query, text, markup)
    elif kind == "credit":
        await safe_edit(query, credit_text(), back_markup())
    elif kind == "contact":
        await safe_edit(query, contact_text(), back_markup())


def main() -> None:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler(["start", "menu"], cmd_start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
