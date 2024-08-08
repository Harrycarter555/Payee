import logging
import os
import base64
import requests
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')

# Initialize logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize bot and updater
bot = Bot(token=TELEGRAM_TOKEN)
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

ASK_FILE_NAME = range(1)

def shorten_url(long_url: str) -> str:
    try:
        response = requests.get(f"https://publicearn.com/api?api={URL_SHORTENER_API_KEY}&url={requests.utils.quote(long_url)}")
        response.raise_for_status()
        data = response.json()
        return data.get("shortenedUrl", long_url)
    except requests.RequestException as e:
        logger.error(f"Error shortening URL: {e}")
        return long_url

def generate_file_opener_url(short_url, file_name):
    if short_url:
        short_url_encoded = base64.b64encode(short_url.encode('utf-8')).decode('utf-8')
        return f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={short_url_encoded}&&{file_name}'
    return None

def start(update: Update, context: CallbackContext):
    if context.args:
        decoded_url = base64.b64decode(context.args[0]).decode('utf-8')
        shortened_link = shorten_url(decoded_url)
        update.message.reply_text(f'Here is your shortened link: {shortened_link}')
    else:
        update.message.reply_text('Welcome! Please use the link provided in the channel.')

def post(update: Update, context: CallbackContext):
    if context.args:
        long_url = context.args[0]
        shortened_url = shorten_url(long_url)
        file_opener_url = generate_file_opener_url(shortened_url, "file_name")
        update.message.reply_text(
            f'File URL processed:\nFile path: {long_url}\nShortened link: {shortened_url}\nFile opener URL: {file_opener_url}\nPost to channel? (yes/no)'
        )
        context.user_data.update({'short_url': shortened_url, 'file_opener_url': file_opener_url})
        return ASK_FILE_NAME
    else:
        update.message.reply_text('Please provide a URL to shorten.')

def ask_file_name(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    if user_response == 'yes':
        update.message.reply_text('Provide the file name:')
        return ASK_FILE_NAME
    else:
        update.message.reply_text('File not posted.')
        return ConversationHandler.END

def handle_file_name(update: Update, context: CallbackContext):
    file_name = update.message.text
    file_opener_url = context.user_data.get('file_opener_url')
    if file_opener_url:
        bot.send_message(chat_id=CHANNEL_ID, text=f'File Name: {file_name}\nAccess: {file_opener_url}')
        update.message.reply_text('File posted to channel.')
    else:
        update.message.reply_text('Failed to retrieve URL.')
    return ConversationHandler.END

# Handlers
dispatcher.add_handler(ConversationHandler(
    entry_points=[CommandHandler('post', post)],
    states={ASK_FILE_NAME: [MessageHandler(Filters.text & ~Filters.command, handle_file_name)]},
    fallbacks=[]
))
dispatcher.add_handler(CommandHandler('start', start))

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return 'ok', 200
    except Exception as e:
        logger.error(f'Error: {e}')
        return 'error', 500

@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/setwebhook', methods=['GET', 'POST'])
def setup_webhook():
    response = requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook', data={'url': WEBHOOK_URL})
    return ('Webhook set up successfully!' if response.status_code == 200 else f'Failed: {response.text}'), response.status_code

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Internal error: {error}')
    return 'Internal server error', 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
