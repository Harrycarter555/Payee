import logging
import os
import base64
from flask import Flask, request, jsonify
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import RpcError

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
FILE_OPENER_BOT_USERNAME = os.getenv('FILE_OPENER_BOT_USERNAME')

# Initialize Pyrogram Client
app_client = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Error handling function
async def handle_error(message: Message, error_message: str):
    try:
        await message.reply(error_message, quote=True)
    except RpcError as e:
        logging.error(f"RPC Error: {e}")
        logging.error(f"Failed to send error message: {error_message}")

# Encode function for base64
async def encode(string: str) -> str:
    return base64.b64encode(string.encode('utf-8')).decode('utf-8')

# Get message ID from forwarded message or link
async def get_message_id(client: Client, message: Message) -> int:
    # Implement the actual logic to extract message ID from the forwarded message or link
    pass

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json(force=True)
    logging.info(f"Received update: {update}")

    try:
        message = Message.de_json(update, app_client)
        if message:
            if message.text and message.text.startswith('/batch'):
                asyncio.run(batch(app_client, message))
            elif message.text and message.text.startswith('/genlink'):
                asyncio.run(link_generator(app_client, message))
    except Exception as e:
        logging.error(f"Error processing update: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ok"}), 200

@app.route('/setwebhook', methods=['GET'])
def set_webhook():
    webhook_url = os.getenv('WEBHOOK_URL')
    try:
        response = app_client.set_webhook(webhook_url)
        if response:
            return "Webhook setup ok"
        else:
            return "Webhook setup failed"
    except Exception as e:
        logging.error(f"Webhook setup error: {e}")
        return "Webhook setup failed", 500

# Batch processing handler
async def batch(client: Client, message: Message):
    while True:
        try:
            first_message = await client.ask(text="Forward the First Message from DB Channel (with Quotes)..\n\nor Send the DB Channel Post Link",
                                             chat_id=message.from_user.id, filters=(filters.forwarded | (filters.text & ~filters.forwarded)), timeout=60)
        except Exception as e:
            await handle_error(message, "An error occurred while handling the file. Please try again later.")
            return

        f_msg_id = await get_message_id(client, first_message)
        if f_msg_id:
            break
        else:
            await handle_error(first_message, "❌ Error\n\nthis Forwarded Post is not from my DB Channel or this Link is taken from DB Channel")
            continue

    while True:
        try:
            second_message = await client.ask(text="Forward the Last Message from DB Channel (with Quotes)..\nor Send the DB Channel Post link",
                                              chat_id=message.from_user.id, filters=(filters.forwarded | (filters.text & ~filters.forwarded)), timeout=60)
        except Exception as e:
            await handle_error(message, "An error occurred while handling the file. Please try again later.")
            return

        s_msg_id = await get_message_id(client, second_message)
        if s_msg_id:
            break
        else:
            await handle_error(second_message, "❌ Error\n\nthis Forwarded Post is not from my DB Channel or this Link is taken from DB Channel")
            continue

    string = f"get-{f_msg_id * abs(client.db_channel.id)}-{s_msg_id * abs(client.db_channel.id)}"
    base64_string = await encode(string)
    link = f"https://t.me/{client.username}?start={base64_string}"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')]])
    await second_message.reply_text(f"<b>Here is your link</b>\n\n{link}", quote=True, reply_markup=reply_markup)

# Link generator handler
async def link_generator(client: Client, message: Message):
    while True:
        try:
            channel_message = await client.ask(text="Forward Message from the DB Channel (with Quotes)..\nor Send the DB Channel Post link",
                                               chat_id=message.from_user.id, filters=(filters.forwarded | (filters.text & ~filters.forwarded)), timeout=60)
        except Exception as e:
            await handle_error(message, "An error occurred while handling the file. Please try again later.")
            return

        msg_id = await get_message_id(client, channel_message)
        if msg_id:
            break
        else:
            await handle_error(channel_message, "❌ Error\n\nthis Forwarded Post is not from my DB Channel or this Link is not taken from DB Channel")
            continue

    base64_string = await encode(f"get-{msg_id * abs(client.db_channel.id)}")
    link = f"https://t.me/{client.username}?start={base64_string}"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')]])
    await channel_message.reply_text(f"<b>Here is your link</b>\n\n{link}", quote=True, reply_markup=reply_markup)

# Run the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
