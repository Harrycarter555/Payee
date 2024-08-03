import os
import base64
import requests
import json
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
from googleapiclient.discovery import build
from google.oauth2 import service_account

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
dispatcher = Dispatcher(bot, None, workers=4)  # Set workers to a positive integer

# Configure logging
logging.basicConfig(level=logging.INFO)

# Set maximum content length to None for unlimited size
app.config['MAX_CONTENT_LENGTH'] = None

# Define states for conversation handler
ASK_POST_CONFIRMATION, ASK_FILE_NAME, ASK_SHORTEN_CONFIRMATION = range(3)

# Function to shorten URL
def shorten_url(long_url: str) -> str:
    api_token = URL_SHORTENER_API_KEY
    encoded_url = requests.utils.quote(long_url)  # URL encode the long URL
    api_url = f"https://publicearn.com/api?api={api_token}&url={encoded_url}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        response_data = response.json()
        if response_data.get("status") == "success":
            short_url = response_data.get("shortenedUrl", "")
            if short_url:
                return short_url
        logging.error("Unexpected response format")
        return long_url
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return long_url

# Function to upload file to Google Drive
def upload_to_drive(file: object, file_name: str):
    try:
        file_metadata = {
            'name': file_name,
            'parents': [GOOGLE_DRIVE_FOLDER_ID]
        }
        media = requests.get(file.file_path).content
        drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        logging.info(f"Uploaded file to Google Drive: {file_name}")
    except Exception as e:
        logging.error(f"Error uploading to Google Drive: {e}")

# Define handlers for commands
def start(update: Update, context: CallbackContext):
    update.message.reply_text('Welcome! Please upload your file.')

def handle_document(update: Update, context: CallbackContext):
    try:
        update.message.reply_text('Processing your file, please wait...')
        
        file = update.message.document.get_file()
        file_url = file.file_path
        file_name = update.message.document.file_name
        
        logging.info(f"Received file URL: {file_url}")

        # Upload file to Google Drive and get the link
        upload_to_drive(update.message.document, file_name)
        drive_link = f"https://drive.google.com/drive/folders/{GOOGLE_DRIVE_FOLDER_ID}?id={file.file_id}"

        # Send Google Drive link to user
        update.message.reply_text(f'File uploaded successfully. Here is your Google Drive link: {drive_link}')

        # Ask user if they want to shorten the link
        update.message.reply_text('Do you want to shorten this link? (yes/no)')
        
        context.user_data['drive_link'] = drive_link
        context.user_data['file_name'] = file_name
        return ASK_SHORTEN_CONFIRMATION

    except Exception as e:
        logging.error(f"Error processing document: {e}")
        update.message.reply_text('An error occurred while processing your file. Please try again later.')
        return ConversationHandler.END

# Post the shortened URL to the channel
def post_to_channel(file_name: str, file_opener_url: str):
    try:
        message = (f'File Name: {file_name}\n'
                   f'Access the file using this link: {file_opener_url}')
        bot.send_message(chat_id=CHANNEL_ID, text=message)
        logging.info(f"Posted to channel: {message}")
    except Exception as e:
        logging.error(f"Error posting to channel: {e}")

# Define handlers for conversation
def ask_shorten_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    if user_response == 'yes':
        drive_link = context.user_data.get('drive_link')
        short_link = shorten_url(drive_link)
        update.message.reply_text(f'Shortened link: {short_link}')
        
        # Ask user if they want to post the shortened link to the channel
        update.message.reply_text('Do you want to post this link to the channel? (yes/no)')
        context.user_data['short_link'] = short_link
        return ASK_POST_CONFIRMATION

    elif user_response == 'no':
        drive_link = context.user_data.get('drive_link')
        update.message.reply_text(f'Your Google Drive link: {drive_link}')
        
        # Ask user if they want to post the link to the channel
        update.message.reply_text('Do you want to post this link to the channel? (yes/no)')
        context.user_data['short_link'] = drive_link
        return ASK_POST_CONFIRMATION

    else:
        update.message.reply_text('Please respond with "yes" or "no".')
        return ASK_SHORTEN_CONFIRMATION

def ask_post_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    if user_response == 'yes':
        file_name = context.user_data.get('file_name')
        file_opener_url = context.user_data.get('short_link')
        post_to_channel(file_name, file_opener_url)
        update.message.reply_text('File posted to channel successfully.')
        return ConversationHandler.END
    elif user_response == 'no':
        update.message.reply_text('The file was not posted.')
        return ConversationHandler.END
    else:
        update.message.reply_text('Please respond with "yes" or "no".')
        return ASK_POST_CONFIRMATION

# Add handlers to dispatcher
dispatcher.add_handler(CommandHandler('start', start))
conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.document, handle_document)],
    states={
        ASK_SHORTEN_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, ask_shorten_confirmation)],
        ASK_POST_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, ask_post_confirmation)],
    },
    fallbacks=[],
)
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
