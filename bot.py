from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes,
                          MessageHandler, filters)
import logging
import json
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === CONFIGURATION ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# === PERSISTENCE FILES ===
MESSAGE_MAP_FILE = "message_map.json"
USER_IDS_FILE = "user_ids.json"
BLOCKED_USERS_FILE = "blocked_users.json"

# === LOGGER SETUP ===
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# === DATA PERSISTENCE FUNCTIONS ===
def load_json_set(filename):
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return set(json.load(f))
    except Exception as e:
        logging.error(f"Error loading {filename}: {e}")
    return set()

def save_json_set(data_set, filename):
    try:
        with open(filename, "w") as f:
            json.dump(list(data_set), f)
    except Exception as e:
        logging.error(f"Error saving {filename}: {e}")

def load_message_map():
    try:
        if os.path.exists(MESSAGE_MAP_FILE):
            with open(MESSAGE_MAP_FILE, "r") as f:
                return {int(k): v for k, v in json.load(f).items()}
    except Exception as e:
        logging.error(f"Error loading message map: {e}")
    return {}

def save_message_map(data_dict):
    try:
        with open(MESSAGE_MAP_FILE, "w") as f:
            json.dump(data_dict, f)
    except Exception as e:
        logging.error(f"Error saving message map: {e}")

# === GLOBAL STATE ===
message_map = load_message_map()
user_ids = load_json_set(USER_IDS_FILE)
blocked_users = load_json_set(BLOCKED_USERS_FILE)

# === COMMAND HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Welcome to YuxtorBot Official!\n\n"
        "If you're looking for any movie, feel free to request it here.\n"
        "We will try our best to provide it for you. 🍿\n\n"
        "This Bot is Created By YuxtorBot Official.",
        parse_mode="Markdown")

async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message

    if user.id in blocked_users:
        return

    user_ids.add(user.id)
    save_json_set(user_ids, USER_IDS_FILE)

    username = f"@{user.username}" if user.username else "No username"

    try:
        sent = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=("📩 New Message Received!\n"
                 "\n"
                 f"From    : {user.first_name}\n"
                 f"Username: {username}\n"
                 f"UserID  : {user.id}\n"
                 "\n"
                 f"{msg.text or '[Non-text message]'}"),
            parse_mode="Markdown")
        message_map[sent.message_id] = user.id
        save_message_map(message_map)
    except Exception as e:
        logging.error(f"Could not forward user message to admin: {e}")

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠ Please reply to a user's message to respond.")
        return

    original_msg_id = update.message.reply_to_message.message_id

    if original_msg_id in message_map:
        user_id = message_map[original_msg_id]
        if user_id in blocked_users:
            await update.message.reply_text("🚫 This user is currently blocked. Cannot send message.")
            return
        try:
            await context.bot.send_message(chat_id=user_id, text=update.message.text)
            logging.info(f"Admin replied to user {user_id}")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to send message: {e}")
    else:
        await update.message.reply_text("❌ Could not find user from this reply.")

async def sendall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text("📝 Please enter the message to send to all users...")
    context.user_data["awaiting_broadcast"] = True

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if context.user_data.get("awaiting_broadcast"):
        context.user_data["awaiting_broadcast"] = False
        text = update.message.text
        count = 0

        for uid in user_ids:
            if uid in blocked_users:
                continue
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                count += 1
            except Exception as e:
                logging.warning(f"Could not send broadcast message to {uid}: {e}")

        await update.message.reply_text(f"✅ Message sent to {count} users.")
    else:
        await update.message.reply_text("⚠ Please reply to a user's message to respond or use /sendall to broadcast.")

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if context.args:
        try:
            uid = int(context.args[0])
            blocked_users.add(uid)
            save_json_set(blocked_users, BLOCKED_USERS_FILE)
            await update.message.reply_text(f"🚫 User {uid} has been blocked.")
        except ValueError:
            await update.message.reply_text("❗ Invalid user ID. Please provide a numeric user ID.")
    else:
        await update.message.reply_text("ℹ Usage: /block <user_id>")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if context.args:
        try:
            uid = int(context.args[0])
            if uid in blocked_users:
                blocked_users.discard(uid)
                save_json_set(blocked_users, BLOCKED_USERS_FILE)
                await update.message.reply_text(f"✅ User {uid} has been unblocked.")
            else:
                await update.message.reply_text(f"ℹ User {uid} is not blocked.")
        except ValueError:
            await update.message.reply_text("❗ Invalid user ID. Please provide a numeric user ID.")
    else:
        await update.message.reply_text("ℹ Usage: /unblock <user_id>")

async def list_blocked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not blocked_users:
        await update.message.reply_text("✅ No blocked users.")
    else:
        users = "\n".join(str(uid) for uid in blocked_users)
        await update.message.reply_text(f"🚫 Blocked Users:\n{users}")

async def post_init(application):
    """Ensure clean startup by deleting any existing webhook"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Webhook deleted - Ready for polling")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors gracefully"""
    error = str(context.error)
    logging.error(f"Update {update} caused error {error}")
    
    if "Conflict" in error:
        logging.warning("⚠ Another bot instance detected. Cleaning up...")
        await context.bot.delete_webhook()
        await asyncio.sleep(5)  # Wait before retrying

def main():
    # Build application with proper initialization
    application = ApplicationBuilder() \
        .token(BOT_TOKEN) \
        .post_init(post_init) \
        .build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sendall", sendall_command))
    application.add_handler(CommandHandler("block", block_user))
    application.add_handler(CommandHandler("unblock", unblock_user))
    application.add_handler(CommandHandler("blocked", list_blocked))

    # Add message handlers
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.User(user_id=ADMIN_ID) & filters.REPLY,
            admin_reply))
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.User(user_id=ADMIN_ID) & ~filters.REPLY,
            handle_admin_input))
    application.add_handler(
        MessageHandler(
            filters.TEXT & (~filters.User(user_id=ADMIN_ID)),
            user_message))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logging.info("🚀 Starting bot...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False
    )

if __name__ == "__main__":
    main()
