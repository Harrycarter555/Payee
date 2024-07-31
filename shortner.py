import os
import requests
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext
from shortener import shorten_url  # Import the shorten_url function

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

if not TELEGRAM_TOKEN or not WEBHOOK_URL:
    logger.error("Environment variables TELEGRAM_TOKEN or WEBHOOK_URL are not set.")
    raise ValueError("Required environment variables are not set.")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Define the start command handler
def start(update: Update, context: CallbackContext):
    update.message.reply_text('Hello, World!')

# Define the document handler
def handle_document(update: Update, context: CallbackContext):
    file = update.message.document.get_file()
    file_url = file.file_path
    short_url = shorten_url(file_url)
    update.message.reply_text(f'Here is your file link: {short_url}')

# Add handlers to dispatcher
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(MessageHandler(Filters.document, handle_document))

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return 'ok', 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return 'Internal Server Error', 500

# Webhook setup route
@app.route('/setwebhook', methods=['GET', 'POST'])
def setup_webhook():
    try:
        response = requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook',
            data={'url': WEBHOOK_URL}
        )
        if response.json().get('ok'):
            return "Webhook setup ok"
        else:
            logger.error(f"Failed to set webhook: {response.json()}")
            return "Webhook setup failed"
    except Exception as e:
        logger.error(f"Error setting up webhook: {e}")
        return "Webhook setup error", 500

if __name__ == '__main__':
    app.run(port=int(os.getenv('PORT', 5000)))
