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

# Check for missing environment variables
if not all([TELEGRAM_TOKEN, WEBHOOK_URL]):
    missing_vars = [var for var in ['TELEGRAM_TOKEN', 'WEBHOOK_URL'] if not os.getenv(var)]
    raise ValueError(f"Environment variables missing: {', '.join(missing_vars)}")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Define the start command handler
def start(update: Update, context: CallbackContext):
    update.message.reply_text('Please upload the file you want to share.')

# Handle file uploads
def handle_file_upload(update: Update, context: CallbackContext):
    try:
        file = update.message.document.get_file()
        file_url = file.file_path

        # Provide the streaming link to the user
        # Note: Telegram file_path is not a direct streaming link, but it can be used for direct file access.
        streaming_link = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_url.replace('/file/bot', '')}"
        update.message.reply_text(f'File uploaded successfully! Here is your streaming link: {streaming_link}')
    except Exception as e:
        logging.error(f"Error handling file upload: {e}", exc_info=True)
        update.message.reply_text('An error occurred while processing the file. Please try again later.')

# Add handlers to dispatcher
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(MessageHandler(Filters.document, handle_file_upload))

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
