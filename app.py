import os
import logging
import json
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Import custom handlers
from handlers import start_handler, handle_file_handler, ask_post_confirmation_handler, ask_file_name_handler

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
    raise ValueError("One or more environment variables are not set.")

# Initialize Telegram bot and dispatcher
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_INFO = json.load(open(GOOGLE_SERVICE_ACCOUNT_FILE))
credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# Set a very large maximum content length
app.config['MAX_CONTENT_LENGTH'] = None  # No limit

# Add handlers to dispatcher
dispatcher.add_handler(start_handler)
dispatcher.add_handler(handle_file_handler)
dispatcher.add_handler(ask_post_confirmation_handler)
dispatcher.add_handler(ask_file_name_handler)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        json_str = request.get_data(as_text=True)
        update = Update.de_json(json.loads(json_str), bot)
        dispatcher.process_update(update)
        return 'ok', 200
    return 'Method Not Allowed', 405

# Define main function to run the Flask app
if __name__ == '__main__':
    # Set webhook URL with Telegram
    bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"Webhook set to: {WEBHOOK_URL}")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
