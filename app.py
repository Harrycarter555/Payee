import os
import json
import requests
from flask import Flask, request, send_from_directory
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters

app = Flask(__name__)

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
    # Send processing message
    processing_message = update.message.reply_text('Processing your file, please wait...')

    try:
        file = update.message.document
        file_name = file.file_name
        file_url = file.get_file().file_path

        # Log file URL for debugging
        print(f"Original file URL: {file_url}")

        # Process URL shortening
        short_url = shorten_url(file_url)
        print(f"Shortened URL: {short_url}")

        # Post the short URL to the channel
        post_to_channel(file_name, short_url)

        # Edit message with the short URL
        processing_message.edit_text(f'File uploaded successfully. Here is your short link: {short_url}')
    except Exception as e:
        processing_message.edit_text(f"An error occurred: {str(e)}")
        print(f"Error: {str(e)}")

# Shorten URL using the URL shortener API
def shorten_url(long_url: str) -> str:
    shortener_url = f'https://publicearn.com/api?api={URL_SHORTENER_API_KEY}&url={long_url}&format=text'
    try:
        response = requests.post(shortener_url)
        if response.status_code == 200:
            return response.text.strip()
        else:
            print(f"Shortener API response: {response.text}")
            return long_url
    except Exception as e:
        print(f"Error shortening URL: {str(e)}")
        return long_url

# Post the shortened URL to the channel
def post_to_channel(file_name: str, short_url: str):
    message = (f'File Name: {file_name}\n'
               f'Click here to access the file: {short_url}\n'
               f'For instructions on how to open the file, visit: https://t.me/{FILE_OPENER_BOT_USERNAME}')
    bot.send_message(chat_id=CHANNEL_ID, text=message)

# Add handlers to dispatcher
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(MessageHandler(Filters.document, handle_document))

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

# Favicon route
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.getcwd(), 'favicon.ico')

# Webhook setup route
@app.route('/setwebhook', methods=['GET', 'POST'])
def setup_webhook():
    webhook_url = WEBHOOK_URL  # Ensure this URL is correct
    response = requests.post(
        f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook',
        data={'url': webhook_url}
    )
    if response.json().get('ok'):
        return "Webhook setup ok"
    else:
        return "Webhook setup failed"

if __name__ == '__main__':
    app.run(port=5000)
