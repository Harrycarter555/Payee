import os
import requests
from flask import Flask, request, send_from_directory
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
import logging

app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')

if not TELEGRAM_TOKEN or not WEBHOOK_URL or not URL_SHORTENER_API_KEY or not CHANNEL_ID or not FILE_OPENER_BOT_USERNAME:
    raise ValueError("One or more environment variables are not set.")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Configure logging
logging.basicConfig(level=logging.INFO)

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

# Define states for conversation handler
ASK_POST_CONFIRMATION, ASK_FILE_NAME = range(2)

# Define the start command handler
def start(update: Update, context: CallbackContext):
    try:
        if context.args:
            encoded_url = context.args[0]
            decoded_url = base64.b64decode(encoded_url).decode('utf-8')
            logging.info(f"Decoded URL: {decoded_url}")

            # Shorten the decoded URL
            shortened_link = shorten_url(decoded_url)
            logging.info(f"Shortened URL: {shortened_link}")

            # Provide information or further processing
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

    # Process URL shortening
    short_url = shorten_url(file_url)
    
    # Ask if user wants to post the shortened URL
    update.message.reply_text(f'File uploaded successfully. Here is your short link: {short_url}\n\nDo you want to post this link to the channel? (yes/no)')
    
    context.user_data['short_url'] = short_url
    return ASK_POST_CONFIRMATION

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
    short_url_encoded = requests.utils.quote(short_url, safe='')
    file_opener_url = f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={short_url_encoded}'

    # Post the shortened URL to the channel
    post_to_channel(file_name, file_opener_url)
    
    update.message.reply_text('File posted to channel successfully.')
    return ConversationHandler.END

# Add handlers to dispatcher
conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.document, handle_document)],
    states={
        ASK_POST_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, ask_post_confirmation)],
        ASK_FILE_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_file_name)],
    },
    fallbacks=[],
)

dispatcher.add_handler(conversation_handler)
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

if __name__ == '__main__':
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2 GB
    app.run(port=5000)
