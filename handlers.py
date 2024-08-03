import os
import base64
import requests
import json
import logging
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler, MessageHandler, Filters

# Load configuration from environment variables
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

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
# Continue from the previous code snippet

def post_to_channel(file_name: str, file_opener_url: str):
    try:
        message = (f'File Name: {file_name}\n'
                   f'Access the file using this link: {file_opener_url}')
        bot.send_message(chat_id=CHANNEL_ID, text=message)
        logging.info(f"Posted to channel: {message}")
    except Exception as e:
        logging.error(f"Error posting to channel: {e}")

# Handle post confirmation
def ask_post_confirmation(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    if text == 'yes':
        short_url = context.user_data.get('short_url')
        file_name = context.user_data.get('file_name')
        
        if short_url and file_name:
            # Generate the file opener bot URL
            file_opener_url = f"https://t.me/{FILE_OPENER_BOT_USERNAME}?start={short_url}"
            
            # Post to the channel
            post_to_channel(file_name, file_opener_url)
            update.message.reply_text('The file link has been posted to the channel.')
        else:
            update.message.reply_text('No URL found. Please upload the file again.')
    elif text == 'no':
        update.message.reply_text('The file link was not posted to the channel.')
    else:
        update.message.reply_text('Please respond with "yes" or "no".')
    
    return ConversationHandler.END

# Ask for the file name in the conversation
def ask_file_name(update: Update, context: CallbackContext):
    update.message.reply_text('Please provide the file name.')
    return ASK_FILE_NAME

# Define conversation handler
conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.document | Filters.photo | Filters.video, handle_file)],
    states={
        ASK_POST_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, ask_post_confirmation)],
        ASK_FILE_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_file_name)],
    },
    fallbacks=[]
)
