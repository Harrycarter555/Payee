import logging
import os
from flask import Flask, request, send_from_directory
import requests
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
import base64
from telethon import TelegramClient
from telethon.sessions import MemorySession
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
USER_ID = os.getenv('USER_ID')

# Check for missing environment variables
if not all([TELEGRAM_TOKEN, WEBHOOK_URL, URL_SHORTENER_API_KEY, CHANNEL_ID, FILE_OPENER_BOT_USERNAME, API_ID, API_HASH, USER_ID]):
    missing_vars = [var for var in ['TELEGRAM_TOKEN', 'WEBHOOK_URL', 'URL_SHORTENER_API_KEY', 'CHANNEL_ID', 'FILE_OPENER_BOT_USERNAME', 'API_ID', 'API_HASH', 'USER_ID'] if not os.getenv(var)]
    raise ValueError(f"Environment variables missing: {', '.join(missing_vars)}")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Initialize Telethon client with in-memory session
telethon_client = TelegramClient(MemorySession(), API_ID, API_HASH)

# Define states for conversation handler
ASK_POST_CONFIRMATION, ASK_FILE_NAME = range(2)

# Shorten URL using the URL shortener API
def shorten_url(long_url: str) -> str:
    api_token = URL_SHORTENER_API_KEY
    encoded_url = requests.utils.quote(long_url)
    api_url = f"https://publicearn.com/api?api={api_token}&url={encoded_url}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        
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

# Define the start command handler
def start(update: Update, context: CallbackContext):
    try:
        if context.args:
            encoded_url = context.args[0]
            decoded_url = base64.b64decode(encoded_url).decode('utf-8')
            logging.info(f"Decoded URL: {decoded_url}")

            shortened_link = shorten_url(decoded_url)
            logging.info(f"Shortened URL: {shortened_link}")

            update.message.reply_text(f'Here is your shortened link: {shortened_link}')
        else:
            update.message.reply_text('Welcome! Please use the link provided in the channel.')
    except Exception as e:
        logging.error(f"Error handling /start command: {e}")
        update.message.reply_text('An error occurred. Please try again later.')

# Define the handler for document uploads
def handle_document(update: Update, context: CallbackContext):
    processing_message = update.message.reply_text('Processing your file, please wait...')
    
    file = update.message.document.get_file()
    file_url = file.file_path
    file_size = update.message.document.file_size

    if file_size > 20 * 1024 * 1024:
        context.user_data['file_path'] = file_url
        update.message.reply_text('File is too large. Uploading directly to your Telegram cloud storage. Please wait...')
        upload_file_to_user_telegram(file_url)
        return ConversationHandler.END
    else:
        short_url = shorten_url(file_url)
        update.message.reply_text(f'File uploaded successfully. Here is your short link: {short_url}\n\nDo you want to post this link to the channel? (yes/no)')
        
        context.user_data['short_url'] = short_url
        return ASK_POST_CONFIRMATION

# Upload file to user's Telegram account
def upload_file_to_user_telegram(file_url: str):
    async def upload_file():
        await telethon_client.start()
        try:
            await telethon_client.send_file(USER_ID, file_url)
            logging.info('File uploaded successfully to user\'s Telegram cloud storage.')
        except Exception as e:
            logging.error(f'Error uploading file: {e}')
        await telethon_client.disconnect()

    with telethon_client:
        telethon_client.loop.run_until_complete(upload_file())

# Post the shortened URL to the channel
def post_to_channel(file_name: str, file_opener_url: str):
    message = (f'File Name: {file_name}\n'
               f'Access the file using this link: {file_opener_url}')
    bot.send_message(chat_id=CHANNEL_ID, text=message)

# Define handlers for conversation
def ask_post_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    if user_response == 'yes':
        update.message.reply_text('Please provide the file name:')
        return ASK_FILE_NAME
    elif user_response == 'no':
        update.message.reply_text('The file was not posted.')
        return ConversationHandler.END
    else:
        update.message.reply_text('Please respond with "yes" or "no".')
        return ASK_POST_CONFIRMATION

def ask_file_name(update: Update, context: CallbackContext):
    file_name = update.message.text
    short_url = context.user_data.get('short_url')

    if short_url:
        short_url_encoded = base64.b64encode(short_url.encode('utf-8')).decode('utf-8')
        file_opener_url = f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={short_url_encoded}&&{file_name}'

        post_to_channel(file_name, file_opener_url)
        
        update.message.reply_text('File posted to channel successfully.')
    else:
        update.message.reply_text('Failed to retrieve the shortened URL.')
    
    return ConversationHandler.END

# Handler for text messages containing URLs
def handle_text_message(update: Update, context: CallbackContext):
    text = update.message.text
    if 'http' in text:  # Simple check for URL
        short_url = shorten_url(text)
        update.message.reply_text(f'Here is your shortened link: {short_url}\n\nDo you want to post this link to the channel? (yes/no)')
        context.user_data['short_url'] = short_url
        return ASK_POST_CONFIRMATION
    else:
        update.message.reply_text('Please send a valid URL.')

# Add handlers to dispatcher
dispatcher.add_handler(MessageHandler(Filters.document, handle_document))
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text_message))

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

# Favicon route
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

# Run the app
if __name__ == '__main__':
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 80)))
