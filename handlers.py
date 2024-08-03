# handlers.py

import base64
import io
import logging
import requests
from googleapiclient.http import MediaIoBaseUpload
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
from app import drive_service, URL_SHORTENER_API_KEY, CHANNEL_ID, FILE_OPENER_BOT_USERNAME

# Define states for conversation handler
ASK_SHORTEN_CONFIRMATION, ASK_POST_CONFIRMATION = range(2)

def shorten_url(long_url: str) -> str:
    api_token = URL_SHORTENER_API_KEY
    encoded_url = requests.utils.quote(long_url)  # URL encode the long URL
    api_url = f"https://publicearn.com/api?api={api_token}&url={encoded_url}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        
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

def upload_to_drive(file_content: bytes, file_name: str):
    try:
        file_metadata = {
            'name': file_name,
            'parents': [GOOGLE_DRIVE_FOLDER_ID]
        }
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/octet-stream')
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        file_id = file.get('id')
        file_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        logging.info(f"Uploaded file to Google Drive: {file_name}")
        return file_link

    except Exception as e:
        logging.error(f"Error uploading to Google Drive: {e}")
        return None

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
        file_content = response.content
        
        # Upload file to Google Drive and get the link
        drive_link = upload_to_drive(file_content, file_name)
        
        if drive_link:
            update.message.reply_text(f'File uploaded successfully. Here is your Google Drive link: {drive_link}')

            # Ask user if they want to shorten the link
            update.message.reply_text('Do you want to shorten this link? (yes/no)')
            
            context.user_data['drive_link'] = drive_link
            return ASK_SHORTEN_CONFIRMATION
        else:
            update.message.reply_text('An error occurred while uploading your file. Please try again later.')
            return ConversationHandler.END

    except Exception as e:
        logging.error(f"Error processing document: {e}")
        update.message.reply_text('An error occurred while processing your file. Please try again later.')
        return ConversationHandler.END

def ask_shorten_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    if user_response == 'yes':
        drive_link = context.user_data.get('drive_link')
        short_link = shorten_url(drive_link)
        update.message.reply_text(f'Shortened link: {short_link}')
        
        # Ask user if they want to post the shortened link to the channel
        update.message.reply_text('Do you want to post this link to the channel? (yes/no)')
        context.user_data['short_link'] = short_link
        return ASK_POST_CONFIRMATION

    elif user_response == 'no':
        drive_link = context.user_data.get('drive_link')
        update.message.reply_text(f'Your Google Drive link: {drive_link}')
        
        # Ask user if they want to post the link to the channel
        update.message.reply_text('Do you want to post this link to the channel? (yes/no)')
        context.user_data['short_link'] = drive_link
        return ASK_POST_CONFIRMATION

    else:
        update.message.reply_text('Please respond with "yes" or "no".')
        return ASK_SHORTEN_CONFIRMATION

def ask_post_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    if user_response == 'yes':
        file_opener_url = context.user_data.get('short_link')
        post_to_channel(file_opener_url)
        update.message.reply_text('File posted to channel successfully.')
        return ConversationHandler.END
    elif user_response == 'no':
        update.message.reply_text('The file was not posted.')
        return ConversationHandler.END
    else:
        update.message.reply_text('Please respond with "yes" or "no".')
        return ASK_POST_CONFIRMATION

def post_to_channel(file_opener_url: str):
    try:
        encoded_url = base64.b64encode(file_opener_url.encode()).decode()
        message = f"https://t.me/{FILE_OPENER_BOT_USERNAME}?start={encoded_url}"
        bot.send_message(chat_id=CHANNEL_ID, text=message)
        logging.info(f"Posted to channel: {message}")
    except Exception as e:
        logging.error(f"Error posting to channel: {e}")

# Define conversation handler
conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.document, handle_document)],
    states={
        ASK_SHORTEN_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, ask_shorten_confirmation)],
        ASK_POST_CONFIRMATION: [MessageHandler(Filters.text & ~Filters.command, ask_post_confirmation)],
    },
    fallbacks=[],
)
