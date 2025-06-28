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
from app.services.user_service import UserService
from app.db.mongo import get_database
from app.services.llm_service import LLMService
from app.services.mongo_memory import ChatMemory

load_dotenv()

router = APIRouter()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ENABLE_WEBHOOK = os.getenv("ENABLE_WEBHOOK", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Initialize bot and app
bot = Bot(token=TELEGRAM_BOT_TOKEN)
app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_chat_action("typing")
    user = update.effective_user
    db = await get_database()
    user_service = UserService(db)
    checking = await user_service.check_and_create(user)
    llm_service = LLMService(db)
    greeting = await llm_service.generate_greeting(
        first_name=user.first_name,
        username=user.username,
        is_new=checking["new_created"],
        language=user.language_code,
    )
    await update.message.reply_text(greeting)


# Message handler (default)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_chat_action("typing")
    user_input = update.message.text
    user = update.effective_user
    db = await get_database()
    llm_service = LLMService(db, user.id)
    response = await llm_service.reply_user_message(user, user_input)
    await update.message.reply_text(response)


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
