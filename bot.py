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

MODES = {"Ucheba": "study", "SPG Rabota": "spg", "Tvorchestvo": "creative", "Obshiy": "general"}
MODE_PROMPTS = {
      "study": "Geologicheskiy fakultet MGU. Geologiya, mineralogiya, petrografiya.",
      "spg": "Logist morskikh perevozok SPG. SPA, marshruty, Obsidian.",
      "creative": "Tvorcheskie proekty, iskusstvo, tekhnologii.",
      "general": "Universalnyy assistent.",
}
SYSTEM_BASE = "Ty personalnyy II-assistent. Polzovatel: student MGU-geolog, logist SPG, zhivet v Niderlandakh. Otvechay po-russki."

def get_note_path(text, mode):
      today = datetime.now().strftime("%Y-%m-%d")
      folders = {"study": "Geologiya MGU", "spg": "SPG Rabota", "creative": "Tvorchestvo", "general": "Vkhodyashchie"}
      title = re.sub(r"[^\w\s-]", "", text[:40]).strip().replace(" ", "_")
      return f"{folders.get(mode, 'Vkhodyashchie')}/{today}_{title}.md"

def save_to_obsidian(text, path, mode):
      try:
                full_path = Path(OBSIDIAN_PATH) / path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(f"---\ncreated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\ntags: [{mode}]\n---\n\n# {text[:60]}\n\n{text}\n", encoding="utf-8")
                return str(full_path)
except Exception as e:
        logger.error(e)
        return None

def ask_claude(user_id, message, mode):
      if user_id not in user_history:
                user_history[user_id] = []
            user_history[user_id].append({"role": "user", "content": message})
    resp = claude_client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=1000, system=SYSTEM_BASE + " " + MODE_PROMPTS.get(mode, ""), messages=user_history[user_id][-20:])
    reply = resp.content[0].text
    user_history[user_id].append({"role": "assistant", "content": reply})
    return reply

def mode_keyboard():
      return ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MODES] + [[KeyboardButton("Sokhranit zametku"), KeyboardButton("Ochistit istoriyu")]], resize_keyboard=True)

async def start(update, context):
      user_mode[update.effective_user.id] = "general"
    await update.message.reply_text("Privet! Vyberi rezhim:", reply_markup=mode_keyboard())

async def handle_message(update, context):
      uid = update.effective_user.id
    text = update.message.text
    mode = user_mode.get(uid, "general")
    if text in MODES:
              user_mode[uid] = MODES[text]
              await update.message.reply_text(f"Rezhim: {text}", reply_markup=mode_keyboard())
              return
          if text == "Ochistit istoriyu":
                    user_history[uid] = []
                    await update.message.reply_text("Ochishcheno", reply_markup=mode_keyboard())
                    return
                if text == "Sokhranit zametku":
                          context.user_data["note"] = True
                          await update.message.reply_text("Napishi zametku:", reply_markup=mode_keyboard())
                          return
                      if context.user_data.get("note"):
                                context.user_data["note"] = False
                                p = get_note_path(text, mode)
                                s = save_to_obsidian(text, p, mode)
                                await update.message.reply_text(f"Sokhraneno: {p}" if s else "Oshibka", reply_markup=mode_keyboard())
                                return
                            await update.message.chat.send_action("typing")
    try:
              await update.message.reply_text(ask_claude(uid, text, mode), reply_markup=mode_keyboard())
except Exception as e:
        await update.message.reply_text("Oshibka, poprobuy eshche raz.")

def main():
      app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
      main()
