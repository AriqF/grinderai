import os
from fastapi import APIRouter, Request, Depends, HTTPException
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
)
from telegram.ext._utils.types import BD
from app.db.mongo import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from dotenv import load_dotenv
from app.services.user_service import UserService
from app.db.mongo import get_database
from app.services.llm_service import LLMService
from app.services.mongo_memory import ChatMemory
from app.services.goals_service import UserGoalService
import asyncio
import textwrap

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


async def handle_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge the button click
    user = update.effective_user
    data = query.data  # e.g. "complete:task123"
    action, task_id = data.split(":")
    db = await get_database()
    goal_service = UserGoalService(db, str(update.effective_user.id))
    user_service = UserService(db)

    if action == "complete":
        exp_incr = 75
        _, task = await asyncio.gather(
            user_service.increase_exp(str(user.id), exp_incr),
            goal_service.update_daily_task(task_id, is_complete=True),
        )
        await query.edit_message_text(
            f"✅ *{task.title}* marked as completed!\n\n_📈 +{exp_incr} EXP_",
            parse_mode="Markdown",
        )
    elif action == "skip":
        exp_decr = 125
        _, task = await asyncio.gather(
            user_service.decrease_exp(str(user.id), exp_decr),
            goal_service.update_daily_task(task_id, is_complete=False),
        )
        await query.edit_message_text(
            f"⏭️ *{task.title}* skipped\n\n_📉 -{exp_decr} EXP_", parse_mode="Markdown"
        )
    else:
        await query.edit_message_text("⚠️ Unknown action.")


async def handle_today_sentiment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        db = await get_database()
        llm_service = LLMService(db, str(user.id))
        data = await llm_service.get_mood_sentiment(user.first_name)
        if not data:
            await update.message.reply_text(
                "There doesn’t seem to be enough emotional context to analyze your mood today. Feel free to share more about your thoughts or experiences when you're ready — I'm here to help you reflect, track, and grow at your own pace"
            )
        parsed = llm_service.mood_sentiment_to_text(data)
        await update.message.reply_text(parsed, parse_mode="Markdown")
        return "OK"
    except Exception as e:
        print("TELEGRAM_CMD_TODAY ERR", e)
        raise ValueError(e)


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = await get_database()
        user_service = UserService(db)
        user = await user_service.get_user_by_id(str(update.effective_user.id))
        first_name = user.get("first_name") or "-"
        last_name = user.get("last_name")
        last_name = (
            "" if not last_name or str(last_name).lower() == "none" else last_name
        )

        exp = int(user.get("exp", 0))
        message = textwrap.dedent(
            f""" 
        🪪 User Profile
        ━━━━━━━━━━━━━━
        👤 Name: {first_name} {last_name}
        🆔 Telegram ID: {user.get("telegram_id", "-")}
        🧬 Level: {user.get("level", 0)}
        ⭐ EXP: {exp} / {((exp//100)+ 1) * 100 }

        _Bot command wont appear as Rune chat history_
        """
        )
        return await update.message.reply_text(message, parse_mode="Markdown")
    except Exception as e:
        raise ValueError(e)


app.add_handler(CommandHandler("start", start_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(handle_task_callback))
app.add_handler(CommandHandler("today", handle_today_sentiment))
app.add_handler(CommandHandler("profile", handle_stats))


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
