# app.py

import os
import requests
import logging
from flask import Flask, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from telegram import Bot
from telegram.ext import Dispatcher

app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

if not TELEGRAM_TOKEN or not WEBHOOK_URL or not URL_SHORTENER_API_KEY or not CHANNEL_ID or not FILE_OPENER_BOT_USERNAME or not GOOGLE_SERVICE_ACCOUNT_FILE or not GOOGLE_DRIVE_FOLDER_ID:
    raise ValueError("One or more environment variables are not set.")

# Initialize Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_google_service_account_credentials():
    if GOOGLE_SERVICE_ACCOUNT_FILE.startswith('http'):
        response = requests.get(GOOGLE_SERVICE_ACCOUNT_FILE)
        response.raise_for_status()
        service_account_info = response.json()
    else:
        with open(GOOGLE_SERVICE_ACCOUNT_FILE) as f:
            service_account_info = json.load(f)
    return service_account_info

SERVICE_ACCOUNT_INFO = get_google_service_account_credentials()
credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=4)

# Configure logging to DEBUG
logging.basicConfig(level=logging.DEBUG)

# Set maximum content length to None for unlimited size
app.config['MAX_CONTENT_LENGTH'] = None

# Import handlers after initializing the necessary components
from handlers import conversation_handler

# Add handlers to dispatcher
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(conversation_handler)

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return 'ok', 200
    except Exception as e:
        logging.error(f'Error processing update: {e}')
        return 'error', 500

# Home route
@app.route('/')
def home():
    return 'Hello, World!'

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
        return "Webhook setup failed"

if __name__ == '__main__':
    app.run(port=5000, debug=True)
