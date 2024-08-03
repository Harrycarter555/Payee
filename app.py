import os
import json
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler

app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

# Validate environment variables
if not TELEGRAM_TOKEN or not WEBHOOK_URL or not URL_SHORTENER_API_KEY or not CHANNEL_ID or not FILE_OPENER_BOT_USERNAME:
    error_message = "One or more environment variables are not set:"
    if not TELEGRAM_TOKEN:
        error_message += "\n- TELEGRAM_TOKEN"
    if not WEBHOOK_URL:
        error_message += "\n- WEBHOOK_URL"
    if not URL_SHORTENER_API_KEY:
        error_message += "\n- URL_SHORTENER_API_KEY"
    if not CHANNEL_ID:
        error_message += "\n- CHANNEL_ID"
    if not FILE_OPENER_BOT_USERNAME:
        error_message += "\n- FILE_OPENER_BOT_USERNAME"
    raise ValueError(error_message)

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Google Drive API if the module is available
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2 import service_account
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    SERVICE_ACCOUNT_INFO = json.load(open(GOOGLE_SERVICE_ACCOUNT_FILE))
    credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
except ImportError as e:
    logging.error(f"ImportError: {e}")
    drive_service = None
except FileNotFoundError as e:
    logging.error(f"FileNotFoundError: {e}")
    drive_service = None

@app.route('/')
def home():
    return "Hello, World!"

# Import handlers here to avoid circular imports
from handlers import start, handle_file, ask_post_confirmation, ask_file_name, conversation_handler

# Add handlers to dispatcher
dispatcher.add_handler(conversation_handler)
dispatcher.add_handler(CommandHandler('start', start))

# Set webhook for Telegram
@app.route('/webhook', methods=['POST'])
def webhook():
    json_update = request.get_json()
    update = Update.de_json(json_update, bot)
    dispatcher.process_update(update)
    return 'ok'

if __name__ == '__main__':
    app.run(debug=True)
