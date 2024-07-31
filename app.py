import os
import requests
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler

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

# Define states for conversation handler
ASK_POST_CONFIRMATION, ASK_FILE_NAME = range(2)

# Define the start command handler
def start(update: Update, context: CallbackContext):
    update.message.reply_text('Upload your file')
    return ConversationHandler.END

# Define the handler for document uploads
def handle_document(update: Update, context: CallbackContext):
    # Send processing message
    processing_message = update.message.reply_text('Processing your file, please wait...')
    
    file = update.message.document.get_file()
    file_url = file.file_path
    
    # Process URL shortening
    short_url = shorten_url(file_url)
    
    # Ask if user wants to post the shortened URL
    update.message.reply_text(f'File uploaded successfully. Here is your short link: {short_url}\n\nDo you want to post this link to the channel? (yes/no)')
    
    context.user_data['short_url'] = short_url
    return ASK_POST_CONFIRMATION

# Confirm if the user wants to post the URL
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

# Get the file name and post to channel
def ask_file_name(update: Update, context: CallbackContext):
    file_name = update.message.text
    short_url = context.user_data.get('short_url')
    
    # Prepare the URL for the file opener bot
    file_opener_url = f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={short_url}'

    # Post the shortened URL to the channel
    post_to_channel(file_name, file_opener_url)
    
    update.message.reply_text('File posted to channel successfully.')
    return ConversationHandler.END

# Shorten URL using the URL shortener API
def shorten_url(long_url: str) -> str:
    shortener_url = f'https://publicearn.com/api?api=d15e1e3029f8e793ad6d02cf3343365ac15ad144&url={long_url}&format=text'
    try:
        response = requests.post(shortener_url)
        if response.status_code == 200:
            return response.text.strip()
        else:
            return long_url
    except Exception as e:
        print(f"Error shortening URL: {e}")
        return long_url

# Post the shortened URL to the channel
def post_to_channel(file_name: str, file_opener_url: str):
    try:
        message = (f'File Name: {file_name}\n'
                   f'Access the file using this link: {file_opener_url}')
        response = bot.send_message(chat_id=CHANNEL_ID, text=message)
        print(f"Message posted to channel successfully. Response: {response}")
    except Exception as e:
        print(f"Error posting to channel: {e}")

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
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok', 200

# Home route
@app.route('/')
def home():
    return 'Hello, World!'

# Webhook setup route
@app.route('/setwebhook', methods=['GET', 'POST'])
def setup_webhook():
    webhook_url = f'{WEBHOOK_URL}'  # Ensure this URL is correct
    response = requests.post(
        f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook',
        data={'url': webhook_url}
    )
    if response.json().get('ok'):
        return "Webhook setup ok"
    else:
        return "Webhook setup failed"

if __name__ == '__main__':
    app.run(port=5000)
