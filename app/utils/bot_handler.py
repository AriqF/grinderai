import os
from fastapi import APIRouter, Request, Depends, HTTPException
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.ext import CallbackContext
from telegram.ext._utils.types import BD
from app.db.mongo import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ENABLE_WEBHOOK = os.getenv("ENABLE_WEBHOOK", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Initialize bot and app
bot = Bot(token=TELEGRAM_BOT_TOKEN)
app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()


# Command handler example
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Aku adalah AI Assistant kamu. Ketikkan sesuatu untuk memulai!"
    )


# Message handler (default)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    await update.message.reply_text(f"Kamu bilang: {user_input}")


app.add_handler(CommandHandler("start", start_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


# Webhook endpoint
@router.post("/webhook")
async def telegram_webhook(
    request: Request, db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, bot)
        await app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run polling or set webhook (to be called from main.py)
async def configure_bot():
    if ENABLE_WEBHOOK:
        if not WEBHOOK_URL:
            raise RuntimeError("WEBHOOK_URL must be set if ENABLE_WEBHOOK is true")
        await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        print("[BOT] Webhook has been set.")
    else:
        print("[BOT] Running in polling mode...")
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
