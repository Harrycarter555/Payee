import os
import json
import logging
import requests
from flask import Flask, request, send_from_directory
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set.")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL environment variable is not set.")
if not URL_SHORTENER_API_KEY:
    raise ValueError("URL_SHORTENER_API_KEY environment variable is not set.")
if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID environment variable is not set.")
if not FILE_OPENER_BOT_USERNAME:
    raise ValueError("FILE_OPENER_BOT_USERNAME environment variable is not set.")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Define the start command handler
def start(update: Update, context: CallbackContext):
    update.message.reply_text('Upload your file')

# Define the handler for document uploads
def handle_document(update: Update, context: CallbackContext):
    processing_message = update.message.reply_text('Processing your file, please wait...')
    file = update.message.document.get_file()
    file_url = file.file_path
    
    # Process URL shortening
    short_url = shorten_url(file_url)
    
    # Post the short URL to the channel
    post_to_channel(short_url)

    # Edit message with the short URL
    processing_message.edit_text(f'File uploaded successfully. Here is your short link: {short_url}')

# Shorten URL using the URL shortener API
def shorten_url(long_url: str) -> str:
    shortener_url = f'https://publicearn.com/api?api=d15e1e3029f8e793ad6d02cf3343365ac15ad144&url={long_url}&format=text'
    try:
        response = requests.post(shortener_url)
        if response.status_code == 200:
            return response.text.strip()
        else:
            logger.error(f"Failed to shorten URL: {response.text}")
            return long_url
    except Exception as e:
        logger.error(f"Exception occurred while shortening URL: {e}")
        return long_url

# Post the shortened URL to the channel
def post_to_channel(short_url: str):
    message = (f'File Name\n'
               f'Click here to access the file: {short_url}\n'
               f'For instructions on how to open the file, visit: https://t.me/{FILE_OPENER_BOT_USERNAME}')
    try:
        bot.send_message(chat_id=CHANNEL_ID, text=message)
        logger.info(f"Message posted to channel with URL: {short_url}")
    except Exception as e:
        logger.error(f"Failed to post message to channel: {e}")

# Add handlers to dispatcher
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(MessageHandler(Filters.document, handle_document))

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("Received webhook request")
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        logger.info("Update processed successfully")
        return 'ok', 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return f"Internal Server Error: {e}", 500

# Home route
@app.route('/')
def home():
    return 'Hello, World!'

# Favicon route
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.getcwd(), 'favicon.ico')

# Webhook setup route
@app.route('/setwebhook', methods=['GET', 'POST'])
def setup_webhook():
    webhook_url = f'https://storagehc.vercel.app/webhook'  # Ensure this URL is correct
    try:
        response = requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook',
            data={'url': webhook_url}
        )
        if response.json().get('ok'):
            logger.info("Webhook setup successful")
            return "Webhook setup ok"
        else:
            logger.error("Webhook setup failed: " + response.text)
            return "Webhook setup failed"
    except Exception as e:
        logger.error(f"Exception during webhook setup: {e}")
        return "Webhook setup failed"

# Lambda handler function
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Hello from Lambda!'})
    }

if __name__ == '__main__':
    app.run(port=5000)
