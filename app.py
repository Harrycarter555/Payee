import os
import json
import requests
from flask import Flask, request, send_from_directory
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler

app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set.")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL environment variable is not set.")
if not URL_SHORTENER_API_KEY:
    raise ValueError("URL_SHORTENER_API_KEY environment variable is not set.")
if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID environment variable is not set.")
if not FILE_OPENER_BOT_USERNAME:
    raise ValueError("FILE_OPENER_BOT_USERNAME environment variable is not set.")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Define the conversation states
CHOOSING, TYPING_REPLY = range(2)

# Define the start command handler
def start(update: Update, context: CallbackContext):
    update.message.reply_text('Upload your file')

# Define the handler for document uploads
def handle_document(update: Update, context: CallbackContext):
    # Send processing message
    processing_message = update.message.reply_text('Processing your file, please wait...')
    context.user_data['file'] = update.message.document.get_file()
    context.user_data['file_url'] = context.user_data['file'].file_path
    context.user_data['processing_message'] = processing_message

    # Ask for confirmation to post the shortened URL
    update.message.reply_text('Do you want to post the shortened link to the channel? (y/n)')

    return CHOOSING

# Handle user response for posting to channel
def handle_choice(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    if text == 'y':
        # Shorten URL
        short_url = shorten_url(context.user_data['file_url'])
        # Ask for the file name
        update.message.reply_text('Please provide the file name for the post.')
        context.user_data['short_url'] = short_url
        return TYPING_REPLY
    else:
        update.message.reply_text('File upload process cancelled.')
        return ConversationHandler.END

# Handle file name input
def handle_file_name(update: Update, context: CallbackContext):
    file_name = update.message.text
    short_url = context.user_data['short_url']
    
    # Post the shortened URL to the channel
    post_to_channel(file_name, short_url)

    # Edit the processing message
    context.user_data['processing_message'].edit_text(f'File uploaded successfully. Here is your short link: {short_url}')

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
        return long_url

# Post the shortened URL to the channel
def post_to_channel(file_name: str, short_url: str):
    message = (f'{file_name}\n'
               f'Click here to access the file: https://t.me/{FILE_OPENER_BOT_USERNAME}?start={short_url}')
    try:
        bot.send_message(chat_id=CHANNEL_ID, text=message)
    except Exception as e:
        print(f"An error occurred while posting to the channel: {e}")

# Define the conversation handler
conv_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.document, handle_document)],
    states={
        CHOOSING: [MessageHandler(Filters.text & ~Filters.command, handle_choice)],
        TYPING_REPLY: [MessageHandler(Filters.text & ~Filters.command, handle_file_name)],
    },
    fallbacks=[CommandHandler('start', start)],
)

# Add handlers to dispatcher
dispatcher.add_handler(conv_handler)

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

# Favicon route
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.getcwd(), 'favicon.ico')

# Webhook setup route
@app.route('/setwebhook', methods=['GET', 'POST'])
def setup_webhook():
    webhook_url = f'https://storagehc.vercel.app/webhook'
    response = requests.post(
        f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook',
        data={'url': webhook_url}
    )
    if response.json().get('ok'):
        return "Webhook setup ok"
    else:
        return "Webhook setup failed"

# Lambda handler function
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Hello from Lambda!'})
    }

if __name__ == '__main__':
    app.run(port=5000)
