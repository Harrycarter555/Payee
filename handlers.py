import logging
import requests
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext

# Define states for conversation handler
ASK_SHORTEN_CONFIRMATION, ASK_POST_CONFIRMATION = range(2)

def upload_to_telegram(file_id: str, file_name: str):
    try:
        # Send the file to the user
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_id}"
        logging.info(f"File URL: {file_url}")
        return file_url
    except Exception as e:
        logging.error(f"Error sending file: {e}")
        return None

def start(update: Update, context: CallbackContext):
    update.message.reply_text('Welcome! Please upload your file.')

def handle_document(update: Update, context: CallbackContext):
    try:
        update.message.reply_text('Processing your file, please wait...')
        
        file = update.message.document.get_file()
        file_id = file.file_id
        file_name = update.message.document.file_name
        
        logging.info(f"Received file ID: {file_id}")

        # Provide the file URL
        file_url = upload_to_telegram(file_id, file_name)
        
        if file_url:
            update.message.reply_text(f'File uploaded successfully. Here is the file URL: {file_url}')

            # Ask user if they want to shorten the link
            update.message.reply_text('Do you want to shorten this link? (yes/no)')
            
            context.user_data['file_url'] = file_url
            return ASK_SHORTEN_CONFIRMATION
        else:
            update.message.reply_text('An error occurred while processing your file. Please try again later.')
            return ConversationHandler.END

    except Exception as e:
        logging.error(f"Error processing document: {e}")
        update.message.reply_text('An error occurred while processing your file. Please try again later.')
        return ConversationHandler.END

def ask_shorten_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    logging.info(f"User response for shorten confirmation: {user_response}")

    if user_response == 'yes':
        file_url = context.user_data.get('file_url')
        # Simulate shortening URL
        short_link = file_url
        update.message.reply_text(f'Shortened link: {short_link}')
        
        # Ask user if they want to post the shortened link to the channel
        update.message.reply_text('Do you want to post this link to the channel? (yes/no)')
        context.user_data['short_link'] = short_link
        return ASK_POST_CONFIRMATION

    elif user_response == 'no':
        file_url = context.user_data.get('file_url')
        update.message.reply_text(f'Your file link: {file_url}')
        
        # Ask user if they want to post the link to the channel
        update.message.reply_text('Do you want to post this link to the channel? (yes/no)')
        context.user_data['short_link'] = file_url
        return ASK_POST_CONFIRMATION

    else:
        update.message.reply_text('Please respond with "yes" or "no".')
        return ASK_SHORTEN_CONFIRMATION

def ask_post_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.lower()
    
    logging.info(f"User response for post confirmation: {user_response}")

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
        message = f"https://t.me/{FILE_OPENER_BOT_USERNAME}?start={file_opener_url}"
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
