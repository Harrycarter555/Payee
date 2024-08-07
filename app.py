import logging
import os
from flask import Flask, request, send_from_directory
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message

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
API_ID = os.getenv('API_ID')  # Your API ID
API_HASH = os.getenv('API_HASH')  # Your API Hash

# Check for missing environment variables
if not all([TELEGRAM_TOKEN, WEBHOOK_URL, CHANNEL_ID, API_ID, API_HASH]):
    missing_vars = [var for var in ['TELEGRAM_TOKEN', 'WEBHOOK_URL', 'CHANNEL_ID', 'API_ID', 'API_HASH'] if not os.getenv(var)]
    raise ValueError(f"Environment variables missing: {', '.join(missing_vars)}")

# Initialize Pyrogram Client
pyrogram_client = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=TELEGRAM_TOKEN)

# Define the start command handler
@pyrogram_client.on_message(filters.command("start"))
async def start(client, message: Message):
    try:
        await message.reply_text('Please forward the file from the channel to this bot to get the download link.')
    except Exception as e:
        logging.error(f"Error handling /start command: {e}")
        await message.reply_text('An error occurred. Please try again later.')

# Define the handler for forwarded documents
@pyrogram_client.on_message(filters.document & filters.forwarded)
async def handle_forwarded_document(client, message: Message):
    try:
        if message.forward_from_chat and message.forward_from_chat.id == int(CHANNEL_ID):
            file_id = message.document.file_id

            # Get file information using Pyrogram
            file_info = await client.get_file(file_id)
            file_path = file_info.file_path

            # Provide the file path directly to the user
            await message.reply_text(f'File path: {file_path}')
        else:
            await message.reply_text('Please forward the file from the specified channel.')
    except Exception as e:
        logging.error(f"Error handling forwarded document: {e}", exc_info=True)
        await message.reply_text('An error occurred while handling the file. Please try again later.')

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = request.get_json(force=True)
        pyrogram_client.process_update(update)
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
    pyrogram_client.start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
