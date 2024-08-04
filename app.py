import os
import base64
import requests
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext

# Initialize Flask app
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
dispatcher = Dispatcher(bot, None, workers=4)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Define states for conversation handler
ASK_FILE_NAME, ASK_SHORTEN_CONFIRMATION, ASK_POST_CONFIRMATION = range(3)

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
                encoded_short_url = base64.b64encode(short_url.encode()).decode()
                return encoded_short_url
        logging.error("Unexpected response format or status")
        return long_url
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return long_url

def post_to_channel(file_opener_url: str, file_name: str):
    try:
        decoded_url = base64.b64decode(file_opener_url).decode()
        
        # Format the message to include direct file name and short link
        message = (
            f"📁 *File Name:* {file_name}\n"
            f"🔗 *Link:* https://t.me/{FILE_OPENER_BOT_USERNAME}?start={file_opener_url}&&{file_name}"
        )
        
        bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode='Markdown'  # Use Markdown for better formatting options
        )
        logging.info(f"Posted to channel: {message}")
    except Exception as e:
        logging.error(f"Error posting to channel: {e}")

def start(update: Update, context: CallbackContext):
    update.message.reply_text('Welcome! Please upload your file.')

def handle_document(update: Update, context: CallbackContext):
    try:
        update.message.reply_text('Processing your file, please wait...')
        
        file = update.message.document.get_file()
        file_url = file.file_path
        file_name = update.message.document.file_name
        
        logging.info(f"Received file URL: {file_url}")

        # Generate a direct download link
        file_link = file_url  # Since Telegram does not provide an actual URL, this will be the file's unique Telegram ID
        
        if file_link:
            context.user_data['file_link'] = file_link
            context.user_data['file_name'] = file_name
            update.message.reply_text(f'File processed successfully. Here is your link: {file_link}')

            # Ask user for the file name
            update.message.reply_text('Please provide the file name for confirmation:')
            return ASK_FILE_NAME
        else:
            update.message.reply_text('An error occurred while processing your file. Please try again later.')
            return ConversationHandler.END

    except Exception as e:
        logging.error(f"Error processing document: {e}")
        update.message.reply_text('An error occurred while processing your file. Please try again later.')
        return ConversationHandler.END

def ask_file_name(update: Update, context: CallbackContext):
    file_name = update.message.text
    context.user_data['file_name'] = file_name
    
    update.message.reply_text(f'You provided the file name as: {file_name}\nDo you want to shorten this link? (yes/no)')
    return ASK_SHORTEN_CONFIRMATION

def ask_shorten_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    if user_response == 'yes':
        file_link = context.user_data.get('file_link')
        short_link = shorten_url(file_link)
        update.message.reply_text(f'Shortened link: {short_link}')
        
        # Ask user if they want to post the shortened link to the channel
        update.message.reply_text('Do you want to post this link to the channel? (yes/no)')
        context.user_data['short_link'] = short_link
        return ASK_POST_CONFIRMATION

    elif user_response == 'no':
        file_link = context.user_data.get('file_link')
        update.message.reply_text(f'Your file link: {file_link}')
        
        # Ask user if they want to post the link to the channel
        update.message.reply_text('Do you want to post this link to the channel? (yes/no)')
        context.user_data['short_link'] = file_link
        return ASK_POST_CONFIRMATION

    else:
        update.message.reply_text('Please respond with "yes" or "no".')
        return ASK_SHORTEN_CONFIRMATION

def ask_post_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    if user_response == 'yes':
        short_link = context.user_data.get('short_link')
        file_name = context.user_data.get('file_name')
        post_to_channel(short_link, file_name)
        update.message.reply_text('File posted to channel successfully.')
        return ConversationHandler.END
    elif user_response == 'no':
        update.message.reply_text('The file was not posted.')
        return ConversationHandler.END
    else:
        update.message.reply_text('Please respond with "yes" or "no".')
        return ASK_POST_CONFIRMATION

# Define conversation handler
conversation_handler = ConversationHandler(
    entry_points=[
        CommandHandler('start', start),  # Handle /start command
        MessageHandler(Filters.document, handle_document)
    ],
    states={
        ASK_FILE_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_file_name)],
        ASK_SHORTEN_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, ask_shorten_confirmation)],
        ASK_POST_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, ask_post_confirmation)],
    },
    fallbacks=[],
)

# Add handlers to dispatcher
dispatcher.add_handler(conversation_handler)

@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/webhook', methods=['POST'])
def webhook():
    logging.info('Webhook received')
    
    try:
        json_data = request.get_json()
        
        if json_data is None:
            logging.error('Invalid JSON format')
            return 'error', 400

        # Create an Update object from the JSON data
        update = Update.de_json(json_data, bot)
        dispatcher.process_update(update)
        return 'ok'
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return 'error', 500

if __name__ == '__main__':
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
