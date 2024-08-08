import logging
import os
import base64
import requests
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
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

# Check for missing environment variables
if not all([TELEGRAM_TOKEN, WEBHOOK_URL, URL_SHORTENER_API_KEY, CHANNEL_ID, FILE_OPENER_BOT_USERNAME]):
    missing_vars = [var for var in ['TELEGRAM_TOKEN', 'WEBHOOK_URL', 'URL_SHORTENER_API_KEY', 'CHANNEL_ID', 'FILE_OPENER_BOT_USERNAME'] if not os.getenv(var)]
    raise ValueError(f"Environment variables missing: {', '.join(missing_vars)}")

# Initialize logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

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
        logger.error("Unexpected response format")
        return long_url
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return long_url

# Generate file opener URL
def generate_file_opener_url(short_url, file_name):
    if short_url:
        short_url_encoded = base64.b64encode(short_url.encode('utf-8')).decode('utf-8')
        file_opener_url = f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={short_url_encoded}&&{file_name}'
        return file_opener_url
    return None

# Define the start command handler
def start(update: Update, context: CallbackContext):
    try:
        if context.args:
            encoded_url = context.args[0]
            decoded_url = base64.b64decode(encoded_url).decode('utf-8')
            logger.info(f"Decoded URL: {decoded_url}")

            shortened_link = shorten_url(decoded_url)
            logger.info(f"Shortened URL: {shortened_link}")

            update.message.reply_text(f'Here is your shortened link: {shortened_link}')
        else:
            update.message.reply_text('Welcome! Please use the link provided in the channel.')
    except Exception as e:
        logger.error(f"Error handling /start command: {e}")
        update.message.reply_text('An error occurred. Please try again later.')

# Define the post command handler
def post(update: Update, context: CallbackContext):
    try:
        if context.args:
            long_url = context.args[0]
            shortened_url = shorten_url(long_url)
            logger.info(f"Shortened URL: {shortened_url}")

            encoded_url = base64.b64encode(shortened_url.encode('utf-8')).decode('utf-8')
            file_opener_url = f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={encoded_url}'

            update.message.reply_text(
                f'Here is your shortened link: {shortened_url}\n'
                f'File opener URL: {file_opener_url}\n'
                'Please provide the file name:'
            )
            context.user_data['short_url'] = shortened_url
            context.user_data['file_opener_url'] = file_opener_url
            return ASK_FILE_NAME
        else:
            update.message.reply_text('Please provide a URL to shorten.')
    except Exception as e:
        logger.error(f"Error handling /post command: {e}")
        update.message.reply_text('An error occurred. Please try again later.')

# Define the handler for document uploads
def handle_document(update: Update, context: CallbackContext):
    processing_message = update.message.reply_text('Processing your file, please wait...')
    
    file = update.message.document.get_file()
    file_url = file.file_path
    file_size = update.message.document.file_size

    context.user_data['file_path'] = file_url

    logger.info(f"Received file with URL: {file_url} and size: {file_size}")

    short_url = shorten_url(file_url)
    if short_url:
        file_name = update.message.document.file_name
        file_opener_url = generate_file_opener_url(short_url, file_name)

        update.message.reply_text(
            f'File uploaded successfully.\n'
            f'File path: {file_url}\n'
            f'Here is your short link: {short_url}\n\n'
            f'File opener URL: {file_opener_url}\n'
            'Do you want to post this link to the channel? (yes/no)'
        )
        context.user_data['short_url'] = short_url
        context.user_data['file_opener_url'] = file_opener_url
        return ASK_POST_CONFIRMATION
    else:
        update.message.reply_text('Failed to shorten the URL. Please try again later.')
        return ConversationHandler.END

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
    file_opener_url = context.user_data.get('file_opener_url')

    if file_opener_url:
        post_to_channel(file_name, file_opener_url)
        update.message.reply_text('File posted to channel successfully.')
    else:
        update.message.reply_text('Failed to retrieve the file opener URL.')
    
    return ConversationHandler.END

# Add handlers to dispatcher
conv_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.document, handle_document)],
    states={
        ASK_POST_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, ask_post_confirmation)],
        ASK_FILE_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_file_name)],
    },
    fallbacks=[]
)

dispatcher.add_handler(conv_handler)
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('post', post))

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return 'ok', 200
    except Exception as e:
        logger.error(f'Error processing update: {e}')
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
    
    if response.status_code == 200:
        return 'Webhook set up successfully!', 200
    else:
        return f'Failed to set up webhook: {response.text}', 500

# Error handling route
@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Internal server error: {error}')
    return 'Internal server error', 500

# Run Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
