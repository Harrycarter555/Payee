import os
import requests
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters

app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')  # URL shortener API key
CHANNEL_ID = os.getenv('CHANNEL_ID')  # Channel ID
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')  # File opener bot username

if not TELEGRAM_TOKEN or not WEBHOOK_URL or not URL_SHORTENER_API_KEY or not CHANNEL_ID or not FILE_OPENER_BOT_USERNAME:
    raise ValueError("One or more environment variables are not set.")

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
    
    # Prepare the URL for the file opener bot
    file_opener_url = f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={short_url}'

    # Post the short URL to the channel
    post_to_channel(update.message.document.file_name, file_opener_url)

    # Edit message with the short URL
    processing_message.edit_text(f'File uploaded successfully. Here is your short link: {file_opener_url}')

# Shorten URL using the URL shortener API
def shorten_url(long_url: str) -> str:
    shortener_url = f'https://publicearn.com/api?api={URL_SHORTENER_API_KEY}&url={long_url}&format=text'
    try:
        response = requests.post(shortener_url)
        if response.status_code == 200:
            return response.text.strip()
        else:
            return long_url
    except Exception as e:
        return long_url

# Post the shortened URL to the channel
def post_to_channel(file_name: str, file_opener_url: str):
    message = (f'File Name: {file_name}\n'
               f'Access the file using this link: {file_opener_url}')
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

# Webhook setup route
@app.route('/setwebhook', methods=['GET', 'POST'])
def setup_webhook():
    webhook_url = f'{WEBHOOK_URL}'  # Ensure this URL is correct
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
