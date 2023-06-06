# import logging
# from telegram import Update
# from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# logging.basicConfig(
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     level=logging.INFO
# )

# async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

# if __name__ == '__main__':
#     proxy_url = 'http://192.168.10.185:22222'
#     application = ApplicationBuilder().token("6004713690:AAHz8olZ6Z4qaODXt5fue3CvaF2VQzCQbms").proxy_url(proxy_url).get_updates_proxy_url(proxy_url).build()
    
#     start_handler = CommandHandler('start', start)
#     application.add_handler(start_handler)
    
#     application.run_polling()


import logging
import geopandas as gpd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
from telegram.error import BadRequest
# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "6004713690:AAHz8olZ6Z4qaODXt5fue3CvaF2VQzCQbms"
PROXY_URL = "http://192.168.10.185:22222"

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Send me your location!")

def handle_location(update: Update, context: CallbackContext) -> None:
    user_location = update.message.location
    context.user_data["location"] = user_location

    question = "Choose an option:"
    options = [("Option 1", "o1"), ("Option 2", "o2"), ("Option 3", "o3")]
    keyboard = [[InlineKeyboardButton(text, callback_data=data)] for text, data in options]

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(question, reply_markup=reply_markup)

def handle_button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    choice = query.data
    location = context.user_data["location"]
    geo_data = gpd.read_file("test.geojson")

    # Process GeoJSON data and user's choice
    result = process_geo_data(geo_data, location, choice)
    query.edit_message_text(f"Your choice: {choice}\nResult: {result}")

def process_geo_data(geo_data, location, choice):
    # Implement your custom logic to extract values from the GeoJSON file
    # based on the user's location and choice.

    # Example: Find the nearest point to the user's location
    user_point = gpd.points_from_xy([location.longitude], [location.latitude])
    nearest = geo_data.distance(user_point[0]).idxmin()
    result = geo_data.iloc[nearest]

    return result

def main() -> None:
    try:
        updater = Updater(TOKEN, request_kwargs={'proxy_url': PROXY_URL})
        dispatcher = updater.dispatcher

        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(MessageHandler(Filters.location, handle_location))
        dispatcher.add_handler(CallbackQueryHandler(handle_button_click))

        updater.start_polling()
        updater.idle()
    except BadRequest:
        print('err')
if __name__ == "__main__":
    main()