from flask import Flask, request, jsonify
import logging
import os
import requests
import hmac
import hashlib
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, PreCheckoutQueryHandler, CallbackContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Telegram Application
application = Application.builder().token(os.getenv('BOT_TOKEN')).build()

# Define your handlers here
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text('Welcome! Use /sample to get a sample file or /buy to purchase the full file.')

async def sample(update: Update, context: CallbackContext):
    sample_file_url = os.getenv('SAMPLE_FILE_URL')
    if not sample_file_url:
        await update.message.reply_text("Sample file URL is not configured.")
        return

    response = requests.get(sample_file_url)
    if response.status_code == 200:
        file = response.content
        await context.bot.send_document(chat_id=update.message.chat_id, document=file)
    else:
        await update.message.reply_text("Failed to retrieve the sample file. Please try again later.")

async def buy(update: Update, context: CallbackContext):
    payment_link = os.getenv('RAZORPAY_PAYMENT_LINK')
    if not payment_link:
        await update.message.reply_text("Payment link is not configured.")
        return
    await update.message.reply_text(f"Click the following link to complete your payment: {payment_link}")

async def precheckout_callback(update: Update, context: CallbackContext):
    query = update.pre_checkout_query
    if query.invoice_payload != 'unique-payload':
        await query.answer(ok=False, error_message="Invalid payload.")
        logger.warning(f"Invalid payload: {query.invoice_payload}")
    else:
        await query.answer(ok=True)

async def successful_payment(update: Update, context: CallbackContext):
    await update.message.reply_text(f'Thank you for your payment! You can download your full file from the following link: {os.getenv("FULL_FILE_LINK")}')

# Register handlers with Application
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("sample", sample))
application.add_handler(CommandHandler("buy", buy))
application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    try:
        json_data = request.get_json()
        if json_data is None:
            logger.warning("Received empty data")
            return 'Bad Request', 400

        update = Update.de_json(json_data, application.bot)
        application.process_update(update)
        return 'OK'
    except Exception as e:
        logger.error(f"Error in Telegram webhook: {e}")
        return 'Internal Server Error', 500

@app.route('/webhook/razorpay', methods=['POST'])
def razorpay_webhook():
    try:
        headers = request.headers
        request_body = request.data.decode('utf-8')
        json_data = request.get_json()
        if json_data is None:
            logger.warning("Received empty data")
            return 'Bad Request', 400

        razorpay_secret = os.getenv('RAZORPAY_SECRET')
        if not razorpay_secret:
            logger.error("Razorpay secret is not configured.")
            return 'Internal Server Error', 500

        razorpay_signature = headers.get('X-Razorpay-Signature')
        if not razorpay_signature:
            logger.error("Razorpay signature is missing from request headers.")
            return 'Unauthorized', 401

        if not validate_signature(request_body, razorpay_signature, razorpay_secret):
            logger.warning("Invalid Razorpay signature")
            return 'Unauthorized', 401

        event_type = json_data.get('event')
        if event_type == 'payment_captured':
            payment_id = json_data.get('payload', {}).get('payment', {}).get('entity', {}).get('id')
            logger.info(f"Payment captured: {payment_id}")

        return 'OK'
    except Exception as e:
        logger.error(f"Error in Razorpay webhook: {e}")
        return 'Internal Server Error', 500

@app.route('/favicon.ico')
def favicon():
    return '', 204

def validate_signature(payload_str, signature, secret):
    generated_signature = hmac.new(
        key=secret.encode('utf-8'),
        msg=payload_str.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(generated_signature, signature)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
