import logging
import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
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
CHANNEL_ID = os.getenv('CHANNEL_ID')

# Check for missing environment variables
if not all([TELEGRAM_TOKEN, WEBHOOK_URL, CHANNEL_ID]):
    missing_vars = [var for var in ['TELEGRAM_TOKEN', 'WEBHOOK_URL', 'CHANNEL_ID'] if not os.getenv(var)]
    raise ValueError(f"Environment variables missing: {', '.join(missing_vars)}")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Define the start command handler
def start(update: Update, context: CallbackContext):
    try:
        update.message.reply_text(
            'Please forward the file from the channel to this bot to get the download link.')
    except Exception as e:
        logging.error(f"Error handling /start command: {e}")
        update.message.reply_text('An error occurred. Please try again later.')

# Define the handler for forwarded documents
def handle_forwarded_document(update: Update, context: CallbackContext):
    try:
        if update.message.forward_from_chat and update.message.forward_from_chat.id == int(CHANNEL_ID):
            file = update.message.document.get_file()
            file_id = update.message.document.file_id
            
            # Fetch file information using file_id
            file_info = bot.get_file(file_id)
            file_path = file_info.file_path
            
            # Logging file path and other details
            logging.info(f"File ID: {file_id}")
            logging.info(f"File Path: {file_path}")
            
            # Provide the file path directly to the user
            update.message.reply_text(f'File path: {file_path}')
        else:
            update.message.reply_text('Please forward the file from the specified channel.')
    except Exception as e:
        logging.error(f"Error handling forwarded document: {e}", exc_info=True)
        update.message.reply_text('An error occurred while handling the file. Please try again later.')

# Add handlers to dispatcher
dispatcher.add_handler(MessageHandler(Filters.document & Filters.forwarded, handle_forwarded_document))
dispatcher.add_handler(CommandHandler('start', start))

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return 'ok', 200
    except Exception as e:
        logging.error(f'Error processing update: {e}', exc_info=True)
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
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
