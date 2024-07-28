import json
import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext

app = Flask(__name__)

# Load configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'your_default_telegram_token')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://your-default-webhook-url')

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Define the start command handler
def start(update: Update, context: CallbackContext):
    update.message.reply_text('Hello, World!')

# Add handlers to dispatcher
dispatcher.add_handler(CommandHandler('start', start))

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok', 200

# Home route
@app.route('/')
def home():
    return 'Hello, World!'

# Lambda handler
def lambda_handler(event, context):
    from werkzeug.serving import run_simple
    run_simple('0.0.0.0', 5000, app)
    return {
        'statusCode': 200,
        'body': json.dumps('Hello, World!')
    }

if __name__ == '__main__':
    app.run(port=5000)
