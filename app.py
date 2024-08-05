import os
import asyncio
import logging
import requests
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Initialize Flask app
app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')
API_HASH = os.getenv('API_HASH')
APP_ID = int(os.getenv('APP_ID'))
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID'))

if not all([TELEGRAM_TOKEN, WEBHOOK_URL, URL_SHORTENER_API_KEY, CHANNEL_ID, FILE_OPENER_BOT_USERNAME,
            API_HASH, APP_ID, BOT_TOKEN, OWNER_ID]):
    error_message = (
        "One or more environment variables are not set. Please ensure the following "
        "environment variables are configured:\n"
        "- TELEGRAM_TOKEN\n"
        "- WEBHOOK_URL\n"
        "- URL_SHORTENER_API_KEY\n"
        "- CHANNEL_ID\n"
        "- FILE_OPENER_BOT_USERNAME\n"
        "- API_HASH\n"
        "- APP_ID\n"
        "- BOT_TOKEN\n"
        "- OWNER_ID"
    )
    raise ValueError(error_message)

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=4)

# Initialize pyrogram bot
xbot = Client('File-Sharing', api_id=APP_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Set maximum content length to 2GB
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB

# Define states for conversation handler
ASK_FILE_NAME, ASK_SHORTEN_CONFIRMATION, ASK_POST_CONFIRMATION = range(3)

START_BUTTONS = [
    [
        InlineKeyboardButton('Source', url='https://github.com/X-Gorn/File-Sharing'),
        InlineKeyboardButton('Project Channel', url='https://t.me/xTeamBots'),
    ],
    [InlineKeyboardButton('Author', url="https://t.me/xgorn")],
]

async def handle_file(update: Update, context: CallbackContext):
    try:
        file = update.message.document.get_file()
        file_url = file.file_path
        file_name = update.message.document.file_name
        file_size = update.message.document.file_size

        if file_size <= 15 * 1024 * 1024:  # 15MB
            await update.message.reply_text(f'File processed successfully. Here is your link: {file_url}')
        else:
            file_link = post_to_channel(file_url, file_name)
            short_link = shorten_url(file_link)
            await update.message.reply_text(f'File processed successfully. Here is your shortened link: {short_link}')
        
        await update.message.reply_text('Please provide the file name for confirmation:')
        return ASK_FILE_NAME
    except Exception as e:
        logging.error(f"Error processing document: {e}")
        await update.message.reply_text('An error occurred while processing your file. Please try again later.')
        return ConversationHandler.END

async def __reply(update: Update, copied):
    msg_id = copied.message_id
    if copied.video:
        unique_idx = copied.video.file_unique_id
    elif copied.photo:
        unique_idx = copied.photo.file_unique_id
    elif copied.audio:
        unique_idx = copied.audio.file_unique_id
    elif copied.document:
        unique_idx = copied.document.file_unique_id
    elif copied.sticker:
        unique_idx = copied.sticker.file_unique_id
    elif copied.animation:
        unique_idx = copied.animation.file_unique_id
    elif copied.voice:
        unique_idx = copied.voice.file_unique_id
    elif copied.video_note:
        unique_idx = copied.video_note.file_unique_id
    else:
        await copied.delete()
        return

    await update.reply_text(
        'Here is Your Sharing Link:',
        True,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton('Sharing Link',
                                  url=f'https://t.me/{FILE_OPENER_BOT_USERNAME}?start={unique_idx.lower()}-{str(msg_id)}')]
        ])
    )
    await asyncio.sleep(0.5)  # Wait to avoid 5 sec flood ban

def shorten_url(long_url: str) -> str:
    api_token = URL_SHORTENER_API_KEY
    encoded_url = requests.utils.quote(long_url, safe='')
    api_url = f"https://publicearn.com/api?api={api_token}&url={encoded_url}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        
        response_data = response.json()
        if response_data.get("status") == "success":
            short_url = response_data.get("shortenedUrl", "")
            if short_url:
                return short_url
        logging.error("Unexpected response format or status")
        return long_url
    except requests.RequestException as e:
        logging.error(f"Request error: {e}")
        return long_url

def post_to_channel(file_url: str, file_name: str) -> str:
    try:
        message = bot.send_document(chat_id=CHANNEL_ID, document=file_url, caption=file_name)
        file_id = message.document.file_id
        file_link = f"https://t.me/{FILE_OPENER_BOT_USERNAME}/{file_id}"
        
        logging.info(f"File uploaded to channel: {file_link}")
        return file_link
    except Exception as e:
        logging.error(f"Error posting to channel: {e}")
        return ""

# Define conversation handler
conversation_handler = ConversationHandler(
    entry_points=[
        CommandHandler('start', lambda update, context: update.message.reply_text('Welcome! Please upload your file.')),
        MessageHandler(Filters.document, handle_file)
    ],
    states={
        ASK_FILE_NAME: [MessageHandler(Filters.text & ~Filters.command, lambda update, context: context.user_data.update({'file_name': update.message.text}) or update.message.reply_text(f'You provided the file name as: {update.message.text}\nDo you want to shorten this link? (yes/no)') or ASK_SHORTEN_CONFIRMATION)],
        ASK_SHORTEN_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, lambda update, context: handle_shorten_confirmation(update, context))],
        ASK_POST_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, lambda update, context: handle_post_confirmation(update, context))]
    },
    fallbacks=[],
)

async def handle_shorten_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    if user_response == 'yes':
        file_link = context.user_data.get('file_link')
        short_link = shorten_url(file_link)
        await update.message.reply_text(f'Shortened link: {short_link}')
        
        # Ask user if they want to post the shortened link to the channel
        await update.message.reply_text('Do you want to post this link to the channel? (yes/no)')
        context.user_data['short_link'] = short_link
        return ASK_POST_CONFIRMATION

    elif user_response == 'no':
        file_link = context.user_data.get('file_link')
        await update.message.reply_text(f'Your file link: {file_link}')
        
        # Ask user if they want to post the link to the channel
        await update.message.reply_text('Do you want to post this link to the channel? (yes/no)')
        context.user_data['short_link'] = file_link
        return ASK_POST_CONFIRMATION

    else:
        await update.message.reply_text('Please respond with "yes" or "no".')
        return ASK_SHORTEN_CONFIRMATION

async def handle_post_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    if user_response == 'yes':
        short_link = context.user_data.get('short_link')
        file_name = context.user_data.get('file_name')
        post_to_channel(short_link, file_name)
        await update.message.reply_text('File posted to channel successfully.')
        return ConversationHandler.END
    elif user_response == 'no':
        await update.message.reply_text('The file was not posted.')
        return ConversationHandler.END
    else:
        await update.message.reply_text('Please respond with "yes" or "no".')
        return ASK_POST_CONFIRMATION

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
    xbot.run()
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
