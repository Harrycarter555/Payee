import os
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application
from handlers import start, handle_file, ask_post_confirmation, ask_file_name, conversation_handler

# Initialize Flask app
app = Flask(__name__)

# Initialize Telegram bot
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
application = Application.builder().token(TOKEN).build()

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_file))
application.add_handler(CallbackQueryHandler(ask_post_confirmation, pattern='^confirm$'))
application.add_handler(CallbackQueryHandler(ask_file_name, pattern='^rename$'))
application.add_handler(conversation_handler())

@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_json()
    update = Update.de_json(json_data, application.bot)
    application.update_queue.put(update)
    return jsonify({'status': 'ok'}), 200

@app.route('/')
def home():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))
