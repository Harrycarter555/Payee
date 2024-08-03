import os
import json
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, ConversationHandler

# Initialize Flask app
app = Flask(__name__)

# Initialize Telegram bot and dispatcher
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Import handlers
from handlers import conversation_handler

# Add handlers to dispatcher
dispatcher.add_handler(conversation_handler)

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        json_str = request.get_data(as_text=True)
        update = Update.de_json(json.loads(json_str), bot)
        dispatcher.process_update(update)
        return 'ok', 200
    return 'Method Not Allowed', 405

if __name__ == '__main__':
    # Set webhook URL with Telegram
    bot.set_webhook(url=os.getenv('WEBHOOK_URL'))
    logging.info(f"Webhook set to: {os.getenv('WEBHOOK_URL')}")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
