from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import CommandHandler, Dispatcher, Filters, MessageHandler, Updater
from telegram.ext import CallbackContext
import config

# Initialize Flask app
app = Flask(__name__)

# Initialize Telegram bot
bot = Bot(token=config.TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Define the start command handler
def start(update: Update, context: CallbackContext):
    update.message.reply_text('Hello, World!')

# Add handlers to dispatcher
dispatcher.add_handler(CommandHandler('start', start))

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok', 200

# Home route
@app.route('/')
def home():
    return 'Hello, World!'

# Set the webhook for Telegram bot
def set_webhook():
    webhook_url = f"{config.WEBHOOK_URL}/webhook"
    bot.set_webhook(url=webhook_url)

if __name__ == '__main__':
    set_webhook()
    app.run(port=5000)  # Use a different port if 5000 doesn't work
