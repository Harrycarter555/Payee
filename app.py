import os
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
from handlers import start, handle_file, ask_post_confirmation, ask_file_name, conversation_handler

# Initialize Flask app
app = Flask(__name__)

# Initialize Telegram bot
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Add handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_file))
dispatcher.add_handler(CallbackQueryHandler(ask_post_confirmation, pattern='^confirm$'))
dispatcher.add_handler(CallbackQueryHandler(ask_file_name, pattern='^rename$'))
dispatcher.add_handler(conversation_handler())

@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_json()
    update = Update.de_json(json_data, updater.bot)
    dispatcher.process_update(update)
    return jsonify({'status': 'ok'}), 200

@app.route('/')
def home():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))
