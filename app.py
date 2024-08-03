import os
import base64
import requests
import json
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
import logging

# Try to import googleapiclient and handle ImportError
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2 import service_account
except ImportError as e:
    logging.error(f"ImportError: {e}")
    raise

app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

# Validate environment variables
if not TELEGRAM_TOKEN or not WEBHOOK_URL or not URL_SHORTENER_API_KEY or not CHANNEL_ID or not FILE_OPENER_BOT_USERNAME:
    raise ValueError("One or more environment variables are not set.")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Set a very large maximum content length
app.config['MAX_CONTENT_LENGTH'] = None  # No limit

# Initialize Google Drive API if the module is available
if 'googleapiclient' in globals():
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    SERVICE_ACCOUNT_INFO = json.load(open(GOOGLE_SERVICE_ACCOUNT_FILE))
    credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
else:
    drive_service = None

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

# Function to upload file to Google Drive if the module is available
def upload_to_google_drive(file_path: str, file_name: str):
    if drive_service is None:
        logging.error("Google Drive service is not initialized.")
        return None

    try:
        media = MediaFileUpload(file_path, resumable=True)
        file_metadata = {
            'name': file_name,
            'parents': [GOOGLE_DRIVE_FOLDER_ID]
        }
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        logging.info(f"Uploaded to Google Drive: {file['webViewLink']}")
        return file['webViewLink']
    except Exception as e:
        logging.error(f"Error uploading to Google Drive: {e}")
        return None

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

# Define the handler for file uploads (including images and documents)
def handle_file(update: Update, context: CallbackContext):
    try:
        update.message.reply_text('Processing your file, please wait...')
        
        # Determine the type of file (document or photo)
        if update.message.document:
            file = update.message.document.get_file()
            file_path = file.download_as_bytearray()
            file_name = update.message.document.file_name
        elif update.message.photo:
            file = update.message.photo[-1].get_file()  # Get the highest resolution photo
            file_path = file.download_as_bytearray()
            file_name = "photo.jpg"  # Default file name for photos
        elif update.message.video:
            file = update.message.video.get_file()  # Get the video file
            file_path = file.download_as_bytearray()
            file_name = update.message.video.file_name or "video.mp4"  # Default file name for videos
        else:
            update.message.reply_text('Unsupported file type.')
            return ConversationHandler.END
        
        # Save the file temporarily
        file_path_name = f'/tmp/{file_name}'
        with open(file_path_name, 'wb') as f:
            f.write(file_path)
        
        # Upload to Google Drive
        google_drive_link = upload_to_google_drive(file_path_name, file_name)
        os.remove(file_path_name)  # Clean up local file
        
        if google_drive_link:
            short_url = shorten_url(google_drive_link)
            logging.info(f"Shortened URL: {short_url}")

            # Send the download link immediately
            update.message.reply_text(f'File uploaded successfully. Here is your download link: {google_drive_link}\n'
                                     f'Here is your short link: {short_url}\n\nDo you want to post this link to the channel? (yes/no)')
            
            # Save data for further processing
            context.user_data['short_url'] = short_url
            context.user_data['file_name'] = file_name
            return ASK_POST_CONFIRMATION
        else:
            update.message.reply_text('Error processing the file.')
            return ConversationHandler.END

    except Exception as e:
        logging.error(f"Error processing file: {e}")
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
    entry_points=[MessageHandler(Filters.document | Filters.photo | Filters.video, handle_file)],
    states={
        ASK_POST_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, ask_post_confirmation)],
        ASK_FILE_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_file_name)],
    },
    fallbacks=[],
)

dispatcher.add_handler(conversation_handler)
dispatcher.add_handler(CommandHandler('start', start))

# Set webhook for Telegram
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        json_str = request.get_data(as_text=True)
        update = Update.de_json(json.loads(json_str), bot)
        dispatcher.process_update(update)
        return 'ok', 200
    return 'Method Not Allowed', 405

# Define main function to run the Flask app
if __name__ == '__main__':
    # Set webhook URL with Telegram
    bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"Webhook set to: {WEBHOOK_URL}")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
