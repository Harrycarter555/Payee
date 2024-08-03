import os
import base64
import requests
from flask import Flask, request
from telegram import Bot, Update, InputFile
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
import logging

app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')

# Validate environment variables
if not TELEGRAM_TOKEN or not WEBHOOK_URL or not URL_SHORTENER_API_KEY or not CHANNEL_ID or not FILE_OPENER_BOT_USERNAME:
    raise ValueError("One or more environment variables are not set.")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Increase the maximum content length to 2 GB
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2 GB

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
        if context.args and len(context.args) == 1:
            combined_encoded_str = context.args[0]
            
            # Decode the combined base64 string
            padded_encoded_str = combined_encoded_str + '=='  # Add padding for base64 compliance
            decoded_str = base64.urlsafe_b64decode(padded_encoded_str).decode('utf-8')
            logging.info(f"Decoded String: {decoded_str}")
            
            # Split into URL and file name using the delimiter
            delimiter = '&&'
            if delimiter in decoded_str:
                decoded_url, file_name = decoded_str.split(delimiter, 1)
                logging.info(f"Decoded URL: {decoded_url}")
                logging.info(f"File Name: {file_name}")

                # Shorten the URL
                shortened_link = shorten_url(decoded_url)
                logging.info(f"Shortened URL: {shortened_link}")

                # Prepare and send message
                message = (f'Here is your shortened link: {shortened_link}\n\n'
                           f'File Name: {file_name}')
                update.message.reply_text(message)
            else:
                update.message.reply_text('Invalid format of the encoded string.')
        else:
            update.message.reply_text('Please provide the encoded string in the command.')
    except Exception as e:
        logging.error(f"Error handling /start command: {e}")
        update.message.reply_text('An error occurred. Please try again later.')

# Define the handler for document uploads
def handle_document(update: Update, context: CallbackContext):
    try:
        update.message.reply_text('Processing your file, please wait...')
        
        file = update.message.document.get_file()
        file_url = file.file_path
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name
        
        logging.info(f"Received file URL: {file_url}")
        logging.info(f"File ID: {file_id}")
        logging.info(f"File Name: {file_name}")

        short_url = shorten_url(file_url)
        
        logging.info(f"Shortened URL: {short_url}")
        
        if not short_url.startswith('http'):
            raise ValueError("Shortened URL is invalid.")
        
        update.message.reply_text(f'File uploaded successfully. Here is your short link: {short_url}\n\nDo you want to post this link to the channel? (yes/no)')
        
        context.user_data['short_url'] = short_url
        context.user_data['file_name'] = file_name
        return ASK_POST_CONFIRMATION

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
    encoded_url = base64.urlsafe_b64encode(short_url.encode()).decode().rstrip('=')
    file_opener_url = f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={encoded_url}&&{file_name}'

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

if __name__ == '__main__':
    app.run(port=5000)
