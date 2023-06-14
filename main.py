import logging
import json
import datetime
import geopandas as gpd
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext, \
    BasePersistence, ConversationHandler, PicklePersistence
from telegram.error import BadRequest

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants for ConversationHandler states
START, ASK_PHONE, ASK_QUESTION_1, ASK_QUESTION_2, ASK_LOCATION, HANDLE_LOCATION = range(6)

TOKEN = "6004713690:AAHz8olZ6Z4qaODXt5fue3CvaF2VQzCQbms"
PROXY_URL = "http://192.168.10.185:22222"

persistence = PicklePersistence(filename='bot_data.pickle')


def start(update: Update, context: CallbackContext):
    user = update.effective_user
    # update.message.reply_text(f"id: {user.id}, username: {user.username}")
    user_data = context.user_data
    # update.message.reply_text(user_data)
    # Check if the user has already signed up
    if user.id in persistence.user_data:
        reply_text = "You have already signed up. Thank you!"
        update.message.reply_text(reply_text)
        return ConversationHandler.END

    reply_text = f"Hello, {user.first_name}! Please provide your ID, phone number, and answer the following questions."

    # Ask for user ID
    update.message.reply_text("Please enter your ID:")
    return ASK_PHONE


# Function to handle user ID input
def ask_phone(update: Update, context: CallbackContext):
    user_data = context.user_data

    # Get the user ID
    user_id = update.message.text.strip()
    user_data['id'] = user_id

    # Ask for phone number
    update.message.reply_text("Please enter your phone number:")
    return ASK_QUESTION_1


# Function to handle phone number input
def ask_question_1(update: Update, context: CallbackContext):
    user_data = context.user_data

    # Get the phone number
    phone_number = update.message.text.strip()
    user_data['phone'] = phone_number

    # Ask the first question
    update.message.reply_text("Question 1: What is your favorite color?", reply_markup=get_color_keyboard())
    return ASK_QUESTION_2


# Function to handle the first question answer
def ask_question_2(update: Update, context: CallbackContext):
    user_data = context.user_data

    # Get the answer to the first question
    answer_1 = update.message.text.strip()
    user_data['answer_1'] = answer_1

    # Ask the second question
    update.message.reply_text("Question 2: What is your favorite animal?", reply_markup=get_animal_keyboard())
    return ASK_LOCATION


# Function to handle the second question answer
def ask_location(update: Update, context: CallbackContext):
    user_data = context.user_data

    # Get the answer to the second question
    answer_2 = update.message.text.strip()
    user_data['answer_2'] = answer_2

    # Ask for the user's location
    update.message.reply_text("Please share your location:", reply_markup=ReplyKeyboardRemove())
    return HANDLE_LOCATION


# Function to handle the user's location input  persistence: BasePersistence, bot: Bot
def handle_location(update: Update, context: CallbackContext):
    user_data = context.user_data
    # update.message.reply_text("Please share your location!")

    # Get the user's location
    location = update.message.location
    user_data['location'] = {
        'latitude': location.latitude,
        'longitude': location.longitude
    }
    # Save user data
    # logger.log(msg=context.user_data)
    print("bot_data", context.bot_data)
    print("user_data", context.user_data)
    # persistence("bot")
    # context.persistence.update_user_data(update.effective_user.id, user_data)
    persistence.update_user_data(user_id=update.effective_user.id, data = user_data)
    update.message.reply_text("Thank you for providing your information! You have successfully signed up.")
    return ConversationHandler.END


# Function to get the multi-choice keyboard for question 1
def get_color_keyboard():
    keyboard = [['Red', 'Blue', 'Green'], ['Yellow', 'Orange', 'Purple']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


# Function to get the multi-choice keyboard for question 2
def get_animal_keyboard():
    keyboard = [['Dog', 'Cat', 'Bird'], ['Elephant', 'Tiger', 'Lion']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


# Function to send scheduled messages
# def send_scheduled_messages(context: CallbackContext):
#     # Retrieve all user data
#     user_data = context.persistence.get_user_data()

#     # Loop through all users
#     for user_id, data in user_data.items():
#         user = context.bot.get_chat(user_id)
#         if 'phone' in data:
#             # Send scheduled message to each user
#             message = f"Hello {user.first_name}! This is a scheduled message from the bot."
#             context.bot.send_message(user_id, message)

# Function to send personalized scheduled messages
def send_scheduled_messages(persistence: persistence, bot: Bot):
    # Retrieve all user data
    user_data = persistence.get_user_data()

    # Loop through all users
    for user_id, data in user_data.items():
        user = bot.get_chat(user_id)
        if 'phone' in data:
            # Customize the message based on user's data
            message = f"Hello {user.first_name}! This is a scheduled message from the bot.\n"
            message += f"Your phone number: {data['phone']}\n"
            message += f"Answer to Question 1: {data['answer_1']}\n"
            message += f"Answer to Question 2: {data['answer_2']}\n"
            # ... add more personalized information
            # message = "Hello..."
            # message = data
            bot.send_message(user_id, message)


def main():
    # Create an instance of Updater and pass the bot token and persistence
    # updater = Updater(TOKEN, persistence=persistence, use_context=True)
    updater = Updater(TOKEN, persistence=persistence, use_context=True)  # , request_kwargs={'proxy_url': PROXY_URL})

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add handlers to the dispatcher
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_PHONE: [MessageHandler(Filters.text, ask_phone)],
            ASK_QUESTION_1: [MessageHandler(Filters.text, ask_question_1)],
            ASK_QUESTION_2: [MessageHandler(Filters.text, ask_question_2)],
            ASK_LOCATION: [MessageHandler(Filters.text, ask_location)],
            HANDLE_LOCATION: [MessageHandler(Filters.location, handle_location)]
        },
        fallbacks=[CommandHandler('cancel', start)]
    )

    dp.add_handler(conv_handler)

    # Start the bot
    updater.start_polling()

    # Schedule periodic messages
    job_queue = updater.job_queue
    job_queue.run_repeating(lambda context: send_scheduled_messages(persistence, context.bot),
                            interval=datetime.timedelta(seconds=60).total_seconds())

    # Run the bot until you press Ctrl-C or the process receives SIGINT, SIGTERM, or SIGABRT
    updater.idle()


if __name__ == '__main__':
    main()
