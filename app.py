import os
import json
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, ConversationHandler
from handlers import start, handle_file, ask_post_confirmation, ask_file_name, conversation_handler

app = Flask(__name__)

# Load configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Validate environment variables
if not TELEGRAM_TOKEN or not WEBHOOK_URL:
    raise ValueError("One or more environment variables are not set.")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Add handlers to dispatcher
dispatcher.add_handler(conversation_handler)
dispatcher.add_handler(CommandHandler('start', start))

# Set webhook for Telegram
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        json_str = request.get_data(as_text=True)
        update = Update.de_json(json.loads(json_str), bot)
        dispatcher.process_update(update)
        return 'OK'
    else:
        return 'Invalid request method', 400

# Run the Flask application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
