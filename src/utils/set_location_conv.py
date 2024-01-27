import logging
from logging.handlers import RotatingFileHandler
from telegram import (
    Update,
)
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.error import BadRequest, Forbidden
from telegram.constants import ParseMode
import requests
import re
import warnings
import database

warnings.filterwarnings("ignore", category=UserWarning)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8",
    level=logging.INFO,
    handlers=[
        RotatingFileHandler(
            "bot_logs.log", maxBytes=512000, backupCount=5
        ),  # File handler to write logs to a file
        logging.StreamHandler(),  # Stream handler to display logs in the console
    ],
)
logger = logging.getLogger("agriWeather-bot")
logging.getLogger("httpx").setLevel(logging.WARNING)

# Constants for ConversationHandler states
ASK_FARM_NAME, ASK_LONGITUDE, ASK_LATITUDE, HANDLE_LAT_LONG = range(4)

MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()
###################################################################


# Start of /set conversation
async def set_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ADMIN_LIST:
        await update.message.reply_text("""Please write the desired user ID or press /cancel 
If you want to specify the location of more than one user, it should be entered as follows:
10354451
951412545
1594745
""",
        )
        return ASK_FARM_NAME
    else:
        return ConversationHandler.END

async def ask_farm_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    target_id = update.message.text
    if target_id == "/cancel":
        await update.message.reply_text("The operation was cancelled!")
        return ConversationHandler.END
    elif target_id in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", target_id)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not target_id:
        await update.message.reply_text(
             "Please write the desired user ID or press /cancel :",
        )
        return ASK_FARM_NAME
    elif len(target_id.split('\n'))==1 and not db.check_if_user_exists(int(target_id)):
        await update.message.reply_text("This user does not exist in the database. Please try again. \n/cancel")
        return ASK_FARM_NAME
    user_data["target"] = target_id.split("\n")
    await update.message.reply_text("""
Enter the garden's name:
  If you tend to specify the location of more than one user, enter as below: 
garden 1
garden 2
garden 3
Pay attention to enter the exact name of the user's garden. Even the persian or English numbers should not be mistaken.
""")
    return ASK_LONGITUDE

async def ask_longitude(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    farm_name = update.message.text
    if len(farm_name.split("\n"))==1:
        farm_names = list(db.get_farms(int(user_data['target'][0])))
        if farm_name not in farm_names:
            await update.message.reply_text(f"The garden's name is wrong. Try again. \n/cancel")
            return ASK_LONGITUDE
        else:
            await update.message.reply_text(f"Enter the value of longitude. \n/cancel")
            user_data["farm_name"] = farm_name
            return ASK_LATITUDE
    elif farm_name == "/cancel":
        await update.message.reply_text("The operation was cancelled!")
        return ConversationHandler.END
    elif farm_name in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm_name)
        await update.message.reply_text("The previous operation was cancelled. Pease try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not farm_name:
        await update.message.reply_text(f"What is the garden's name? \n/cancel")
        return ASK_LONGITUDE
    elif len(user_data['target']) != len(farm_name.split('\n')):
        db.log_activity(user.id, "error - farm_name list not equal to IDs", farm_name)
        await update.message.reply_text("The number of id's and the name of the gardens are not the same. Please start again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    user_data["farm_name"] = farm_name.split('\n')
    await update.message.reply_text("""
Enter the related google map links.
One line should be considered for each link.Only links with the following format are acceptable.
https://goo.gl/maps/3Nx2zh3pevaz9vf16
""")
    return ASK_LATITUDE

async def ask_latitude(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    target = user_data["target"]
    farm_name = user_data["farm_name"]
    longitude = update.message.text
    if longitude == "/cancel":
        await update.message.reply_text("The operation was cancelled!")
        return ConversationHandler.END
    elif longitude in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", longitude)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not longitude:
        await update.message.reply_text("""
If you entered one id, now enter the value of longitude. If you have more than one id, enter the related google map links.
One line should be considered for each link. Only links with the following format are acceptable.
https://goo.gl/maps/3Nx2zh3pevaz9vf16
""")
        return ASK_LATITUDE
    elif len(target) == 1 and longitude.replace(".", "").isdecimal() == False:
        await update.message.reply_text("\n\n <b>مقدار Longitude وارد شده قابل قبول نیست. طول و عرض جغرافیایی باید اعداد صحیح یا اعشار باشند.\nدوباره تلاش کنید.</b> \n\n", parse_mode=ParseMode.HTML)
        return ASK_LATITUDE
    elif len(target) == 1:
        user_data["long"] = longitude
        await update.message.reply_text(f"what's the latitude of {user_data['target']}?\ndo you want to /cancel ?")
        return HANDLE_LAT_LONG
    else:
        links = longitude.split("\n")
        if len(user_data['target']) != len(links):
            db.log_activity(user.id, "error - links list not equal to IDs", farm_name)
            await update.message.reply_text("The number of links and ids are not the same. Please try again.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        elif not all(link.startswith("https://goo.gl") for link in links):
            db.log_activity(user.id, "error - links not valid", farm_name)
            await update.message.reply_text("The links are not acceptable. Please start again.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        with requests.session() as s:
            final_url = [s.head(link, allow_redirects=True).url for link in links]
        result = [re.search("/@-?(\d+\.\d+),(\d+\.\d+)", url) for url in final_url]
        for i, user_id in enumerate(user_data['target']):
            try:
                db.set_user_attribute(int(user_id), f"farms.{user_data['farm_name'][i]}.location.latitude", float(result[i].group(1)))
                db.set_user_attribute(int(user_id), f"farms.{user_data['farm_name'][i]}.location.longitude", float(result[i].group(2)))
                await context.bot.send_message(chat_id=int(user_id), text=f"The location of your garden named{user_data['farm_name'][i]} is registered.")
                await context.bot.send_location(chat_id=int(user_id), latitude=float(result[i].group(1)), longitude=float(result[i].group(2)))
                await context.bot.send_message(chat_id=user.id, text=f"The location of the garden{user_id} named {user_data['farm_name'][i]} is registered.")
                await context.bot.send_location(chat_id=user.id, latitude=float(result[i].group(1)), longitude=float(result[i].group(2)))
            except Forbidden:
                await context.bot.send_message(chat_id=user.id, text=f"{user_id} blocked the bot")
                db.set_user_attribute(user_id, "blocked", True)
            except BadRequest:
                await context.bot.send_message(chat_id=user.id, text=f"chat with {user_id} not found. was the user id correct?")
            except KeyError:
                await context.bot.send_message(chat_id=user.id, text=f"{user_id} doesn't have a farm called\n {user_data['farm_name'][i]} \nor user doesn't exist.")
        return ConversationHandler.END

async def handle_lat_long(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    latitude = update.message.text
    if latitude == "/cancel":
        await update.message.reply_text("The operation was cancelled!")
        return ConversationHandler.END
    elif latitude in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", latitude)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not latitude:
        await update.message.reply_text(f"what's the latitude of {latitude}? \ndo you want to /cancel ?")
        return HANDLE_LAT_LONG
    elif latitude.replace(".", "").isdecimal() == False:
        await update.message.reply_text("\n\n <b>The value of the entered Latitude is not acceptable. The geographic length and width should be integer or decimal. Please try again.</b> \n\n", parse_mode=ParseMode.HTML)
        return HANDLE_LAT_LONG
    user_data["lat"] = latitude
    db.set_user_attribute(int(user_data["target"][0]), f"farms.{user_data['farm_name']}.location.longitude", float(user_data["long"]))
    db.set_user_attribute(int(user_data["target"][0]), f"farms.{user_data['farm_name']}.location.latitude", float(user_data["lat"]))
    db.set_user_attribute(int(user_data["target"][0]), f"farms.{user_data['farm_name']}.link-status", "Verified")
    db.log_activity(user.id, "set a user's location", user_data["target"][0])
    for admin in ADMIN_LIST:
        await context.bot.send_message(chat_id=admin, text=f"Location of farm {user_data['farm_name']} belonging to {user_data['target'][0]} was set")
        await context.bot.send_location(chat_id=admin, latitude=float(user_data["lat"]), longitude=float(user_data["long"]))
    try:
        await context.bot.send_message(chat_id=int(user_data["target"][0]), text=f"The location of your garden named {user_data['farm_name']} was registered.")
        await context.bot.send_location(chat_id=int(user_data["target"][0]), latitude=float(user_data["lat"]), longitude=float(user_data["long"]))
    except (BadRequest, Forbidden):
        db.set_user_attribute(int(user_data["target"][0]), "blocked", True)
        await context.bot.send_message(chat_id=user.id, text=f"Location wasn't set. User may have blocked the bot.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The operation was cancelled!")
    return ConversationHandler.END


set_location_handler = ConversationHandler(
        entry_points=[CommandHandler("set", set_loc)],
        states={
            ASK_FARM_NAME: [MessageHandler(filters.ALL, ask_farm_name)],
            ASK_LONGITUDE: [MessageHandler(filters.ALL, ask_longitude)],
            ASK_LATITUDE: [MessageHandler(filters.ALL, ask_latitude)],
            HANDLE_LAT_LONG: [MessageHandler(filters.ALL, handle_lat_long)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )