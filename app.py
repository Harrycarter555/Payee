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
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')  # Ensure this is correctly set
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')  # Ensure this is correctly set

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set.")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL environment variable is not set.")
if not URL_SHORTENER_API_KEY:
    raise ValueError("URL_SHORTENER_API_KEY environment variable is not set.")
if not CHANNEL_USERNAME:
    raise ValueError("CHANNEL_USERNAME environment variable is not set.")
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

    file = update.message.document.get_file()
    file_url = file.file_path
    
    # Process URL shortening
    short_url = shorten_url(file_url)
    
    # Post to the channel with a link to the file opener bot
    bot.send_message(
        chat_id=f'@{CHANNEL_USERNAME}',
        text=(
            f"Here is your file link: {short_url}\n"
            f"To open the file, click [here](https://t.me/{FILE_OPENER_BOT_USERNAME}?start={short_url}).\n"
            f"How to open Tutorial: [Tutorial link](tutorial_link_here)"
        ),
        parse_mode='Markdown'
    )

    # Edit message with the short URL
    processing_message.edit_text(f'File uploaded successfully. Here is your short link: {short_url}')

# Shorten URL using the URL shortener API
def shorten_url(long_url: str) -> str:
    shortener_url = f'https://publicearn.com/api?api={URL_SHORTENER_API_KEY}&url={long_url}&format=text'
    try:
        response = requests.get(shortener_url)
        if response.status_code == 200:
            return response.text.strip()  # Response contains the short URL as plain text
        else:
            return long_url
    except Exception as e:
        print(f"Error shortening URL: {e}")  # Log the error
        return long_url

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
    response = requests.post(
        f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook',
        data={'url': WEBHOOK_URL}
    )
    if response.json().get('ok'):
        return "Webhook setup ok"
    else:
        return f"Webhook setup failed: {response.json().get('description')}"

if __name__ == '__main__':
    app.run(port=5000)
