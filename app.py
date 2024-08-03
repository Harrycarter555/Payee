# app.py
import os
import json
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, ConversationHandler
from googleapiclient.discovery import build
from google.oauth2 import service_account

app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')
GOOGLE_DRIVE_FILE_URL = os.getenv('GOOGLE_DRIVE_FILE_URL')

# Validate environment variables
if not TELEGRAM_TOKEN or not WEBHOOK_URL or not URL_SHORTENER_API_KEY or not CHANNEL_ID or not FILE_OPENER_BOT_USERNAME or not GOOGLE_DRIVE_FILE_URL:
    raise ValueError("One or more environment variables are not set.")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Google Drive API if the module is available
try:
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    SERVICE_ACCOUNT_INFO = json.loads(GOOGLE_DRIVE_FILE_URL)
    credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
except Exception as e:
    logging.error(f"Error initializing Google Drive API: {e}")
    drive_service = None

from handlers import start, handle_file, ask_post_confirmation, ask_file_name, conversation_handler

# Add handlers to dispatcher
dispatcher.add_handler(conversation_handler)
dispatcher.add_handler(CommandHandler('start', start))

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data(as_text=True)
        update = Update.de_json(json.loads(json_str), bot)
        dispatcher.process_update(update)
    except Exception as e:
        logging.error(f"Error processing update: {e}")
    return '', 200

@app.route('/')
def index():
    return 'Bot is running', 200

if __name__ == '__main__':
    app.run()
