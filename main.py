import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

if __name__ == '__main__':
    proxy_url = 'http://192.168.10.185:22222'
    application = ApplicationBuilder().token("6004713690:AAHz8olZ6Z4qaODXt5fue3CvaF2VQzCQbms").proxy_url(proxy_url).get_updates_proxy_url(proxy_url).build()
    
    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)
    
    application.run_polling()

