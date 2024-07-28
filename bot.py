import os
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from search_download import search_and_download  # Assuming search_and_download function is defined in search_download.py

# Function to handle the /start command
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hi! I am your file bot. Send me the file name to search and download.')

# Function to handle file search and download
def handle_file_download(update: Update, context: CallbackContext) -> None:
    file_name = update.message.text
    chat_id = update.message.chat_id

    # Call the search_and_download function
    search_and_download(file_name)

    # Check if the file was downloaded successfully
    download_path = os.path.join("downloads", f"{file_name}")
    if os.path.exists(download_path):
        context.bot.send_document(chat_id=chat_id, document=open(download_path, 'rb'))
        os.remove(download_path)  # Remove the file after sending

# Function to handle errors
def error(update: Update, context: CallbackContext) -> None:
    print(f"Update {update} caused error {context.error}")

# Main function to run the bot
def main() -> None:
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token
    updater = Updater("YOUR_BOT_TOKEN", use_context=True)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Register command handlers
    dispatcher.add_handler(CommandHandler("start", start))

    # Register message handler for file searches
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_file_download))

    # Register error handler
    dispatcher.add_error_handler(error)

    # Start the Bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()