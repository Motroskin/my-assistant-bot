import os
import re
import logging
from datetime import datetime
from pathlib import Path
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OBSIDIAN_PATH = os.getenv("OBSIDIAN_PATH", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
user_history = {}
user_mode = {}

MODES = {"📚 Учёба": "study", "🚢 СПГ": "spg", "🎨 Творчество": "creative", "💬 Общий": "general"}
PROMPTS = {
    "study": "Ты помогаешь студенту геологического факультета МГУ. Геология, минералогия, петрография.",
    "spg": "Ты помогаешь логисту морских перевозок СПГ. SPA, маршруты, документация.",
    "creative": "Ты помогаешь с творческими проектами, искусством и новыми технологиями.",
    "general": "Ты универсальный персональный ассистент.",
}
SYSTEM = "Ты персональный ИИ-ассистент Егора. Он студент МГУ-геолог и логист СПГ. Отвечай по-русски, кратко и по делу."

def note_path(text, mode):
    today = datetime.now().strftime("%Y-%m-%d")
    dirs = {"study": "Геология_МГУ", "spg": "СПГ_Работа", "creative": "Творчество", "general": "Входящие"}
    title = re.sub(r"[^\w\s-]", "", text[:40]).strip().replace(" ", "_")
    return f"{dirs.get(mode,'Входящие')}/{today}_{title}.md"

def save_note(text, path, mode):
    try:
        p = Path(OBSIDIAN_PATH) / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"---\ncreated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\ntags: [{mode}]\n---\n\n{text}\n", encoding="utf-8")
        return str(p)
    except Exception as e:
        logger.error(e)
        return None

def ask(uid, message, mode):
    if uid not in user_history:
        user_history[uid] = []
    user_history[uid].append({"role": "user", "content": message})
    r = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=SYSTEM + " " + PROMPTS.get(mode, ""),
        messages=user_history[uid][-20:]
    )
    reply = r.content[0].text
    user_history[uid].append({"role": "assistant", "content": reply})
    return reply

def kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(m)] for m in MODES] + [[KeyboardButton("📝 Заметка"), KeyboardButton("🗑 Очистить")]],
        resize_keyboard=True
    )

async def start(update, context):
    user_mode[update.effective_user.id] = "general"
    await update.message.reply_text("👋 Привет! Я твой ассистент.\nВыбери режим:", reply_markup=kb())

async def handle(update, context):
    uid = update.effective_user.id
    text = update.message.text
    mode = user_mode.get(uid, "general")
    if text in MODES:
        user_mode[uid] = MODES[text]
        await update.message.reply_text(f"Режим: {text}", reply_markup=kb())
        return
    if text == "🗑 Очистить":
        user_history[uid] = []
        await update.message.reply_text("История очищена ✓", reply_markup=kb())
        return
    if text == "📝 Заметка":
        context.user_data["save"] = True
        await update.message.reply_text("Напиши заметку — сохраню в Obsidian:", reply_markup=kb())
        return
    if context.user_data.get("save"):
        context.user_data["save"] = False
        p = note_path(text, mode)
        s = save_note(text, p, mode)
        await update.message.reply_text(f"✅ Сохранено: {p}" if s else "⚠️ Ошибка сохранения", reply_markup=kb())
        return
    await update.message.chat.send_action("typing")
    try:
        await update.message.reply_text(ask(uid, text, mode), reply_markup=kb())
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("Ошибка, попробуй ещё раз.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
