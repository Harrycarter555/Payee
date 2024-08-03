import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Define your states
CHOOSING, TYPING_REPLY = range(2)

# Load Google Drive API credentials
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome! Send me a file.")

def handle_file(update: Update, context: CallbackContext):
    # Handle file processing
    update.message.reply_text("File received!")

def ask_post_confirmation(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data='confirm')],
        [InlineKeyboardButton("No", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.message.reply_text('Do you want to proceed?', reply_markup=reply_markup)
    return CHOOSING

def ask_file_name(update: Update, context: CallbackContext):
    update.callback_query.message.reply_text('Please send me the new file name.')
    return TYPING_REPLY

def conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [CallbackQueryHandler(ask_post_confirmation)],
            TYPING_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_file_name)],
        },
        fallbacks=[],
        allow_reentry=True
    )
