import os
import logging
from telethon import TelegramClient
from telethon.tl.functions.messages import SendMediaRequest
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext

# Initialize Flask app
app = Flask(__name__)

# Load configuration from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
CHANNEL_ID = os.getenv('CHANNEL_ID')

if not API_ID or not API_HASH or not BOT_TOKEN or not WEBHOOK_URL or not CHANNEL_ID:
    raise ValueError("One or more environment variables are not set.")

# Initialize Telegram bot
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=4)

# Initialize Telethon client
client = TelegramClient('session_name', API_ID, API_HASH)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Set maximum content length to 2GB
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB

def upload_file_to_channel(file_path: str, file_name: str):
    try:
        # Connect to Telethon client
        client.connect()
        if not client.is_user_authorized():
            client.send_code_request(phone_number)  # Use phone number for login
            client.sign_in(phone_number, code)  # Code received from SMS

        # Upload the file
        client.send_file(
            entity=CHANNEL_ID,
            file=file_path,
            caption=f"File Name: {file_name}"
        )
        logging.info(f"File uploaded successfully: {file_path}")

    except Exception as e:
        logging.error(f"Error uploading file: {e}")

def start(update: Update, context: CallbackContext):
    update.message.reply_text('Welcome! Please upload your file.')

def handle_document(update: Update, context: CallbackContext):
    try:
        update.message.reply_text('Processing your file, please wait...')
        
        file = update.message.document.get_file()
        file_url = file.file_path
        file_name = update.message.document.file_name
        
        logging.info(f"Received file URL: {file_url}")

        # Download file content
        response = requests.get(file_url)
        
        if response.status_code == 200:
            # Save the file locally
            file_path = f"/tmp/{file_name}"  # Use /tmp for Lambda environment
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            # Provide download link
            file_link = file_url
            context.user_data['file_link'] = file_link
            context.user_data['file_name'] = file_name
            
            update.message.reply_text(f'File processed successfully. Here is your link: {file_link}')
            update.message.reply_text('Please provide the file name for confirmation:')
            return ASK_FILE_NAME
        else:
            update.message.reply_text('Failed to download the file. Please try again later.')
            return ConversationHandler.END

    except Exception as e:
        logging.error(f"Error processing document: {e}")
        update.message.reply_text('An error occurred while processing your file. Please try again later.')
        return ConversationHandler.END

def ask_file_name(update: Update, context: CallbackContext):
    file_name = update.message.text
    context.user_data['file_name'] = file_name
    
    update.message.reply_text(f'You provided the file name as: {file_name}\nDo you want to post this file to the channel? (yes/no)')
    return ASK_POST_CONFIRMATION

def ask_post_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    if user_response == 'yes':
        file_path = f"/tmp/{context.user_data.get('file_name')}"
        file_name = context.user_data.get('file_name')
        upload_file_to_channel(file_path, file_name)
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
