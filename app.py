import logging
import os
import base64
import requests
from flask import Flask, request, send_from_directory
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Enable Flask debugging
app.debug = True

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')

# Check for missing environment variables
if not all([TELEGRAM_TOKEN, WEBHOOK_URL, URL_SHORTENER_API_KEY, CHANNEL_ID, FILE_OPENER_BOT_USERNAME]):
    missing_vars = [var for var in ['TELEGRAM_TOKEN', 'WEBHOOK_URL', 'URL_SHORTENER_API_KEY', 'CHANNEL_ID', 'FILE_OPENER_BOT_USERNAME'] if not os.getenv(var)]
    raise ValueError(f"Environment variables missing: {', '.join(missing_vars)}")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

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
        update.message.reply_text(
            'Please upload your file directly to your Telegram cloud storage and then provide the file URL here.\n'
            'You can upload your file by sending it to your own Telegram chat.')
    except Exception as e:
        logging.error(f"Error handling /start command: {e}")
        update.message.reply_text('An error occurred. Please try again later.')

# Define the handler for document uploads
def handle_document(update: Update, context: CallbackContext):
    file = update.message.document.get_file()
    file_url = file.file_path

    # Process the file URL
    context.user_data['file_url'] = file_url
    short_url = shorten_url(file_url)
    update.message.reply_text(f'File uploaded successfully. Here is your download link: {file_url}\n\nHere is your shortened URL: {short_url}\n\nDo you want to post this link to the channel? (yes/no)')
    context.user_data['short_url'] = short_url
    return ASK_POST_CONFIRMATION

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

# Post the shortened URL to the channel
def post_to_channel(file_name: str, file_opener_url: str):
    message = (f'File Name: {file_name}\n'
               f'Access the file using this link: {file_opener_url}')
    bot.send_message(chat_id=CHANNEL_ID, text=message)

# Add handlers to dispatcher
dispatcher.add_handler(MessageHandler(Filters.document, handle_document))
dispatcher.add_handler(CommandHandler('start', start))

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
    app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # Set max file size to 25MB
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
