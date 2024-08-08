import logging
import os
import requests
from flask import Flask, request, send_from_directory
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

    # Ensure that file_url is saved
    context.user_data['file_url'] = file_url

    logging.info(f"Received file with URL: {file_url} and size: {file_size}")

    if file_size > 20 * 1024 * 1024:
        update.message.reply_text('File is too large. Uploading directly to the cloud storage. Please wait...')
        # Directly handle large files (e.g., post to channel) without uploading to user cloud storage
        return ConversationHandler.END
    else:
        short_url = shorten_url(file_url)
        if short_url:
            # Notify user with the shortened URL only
            update.message.reply_text(
                f'File uploaded successfully.\n'
                f'Here is your short link: {short_url}\n\n'
                'Do you want to post this link to the channel? (yes/no)'
            )
            context.user_data['short_url'] = short_url
            return ASK_POST_CONFIRMATION
        else:
            # Handle case where URL shortening fails
            update.message.reply_text('Failed to shorten the URL. Please try again later.')
            return ConversationHandler.END

# Define the /post command handler
def post_command(update: Update, context: CallbackContext):
    if context.user_data.get('short_url'):
        file_opener_url = f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={context.user_data["short_url"]}'
        post_to_channel(file_opener_url)
        update.message.reply_text('The link has been posted to the channel.')
    else:
        update.message.reply_text('No link to post. Please start over.')

    return ConversationHandler.END

# Define the function to post to the channel
def post_to_channel(short_url):
    bot.send_message(chat_id=CHANNEL_ID, text=f'File link: {short_url}')

# Define handlers for conversation
conv_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.document, handle_document)],
    states={
        ASK_POST_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, post_command)],
    },
    fallbacks=[]
)

dispatcher.add_handler(conv_handler)
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('post', post_command))

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

# Initialize and run the Flask app
if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Start Flask app
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
