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
from telegram.constants import ParseMode
import warnings
import database
from .keyboards import (
    manage_farms_keyboard,
    farms_list_reply,
)

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
VIEW_FARM = range(1)
MENU_CMDS = ['✍ sign up', '📤 invite others', '🖼 visit the farms', '➕add farm', '🗑 delete farm', '✏️ edit the farms', '🌦 ask for meteorological information', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
###################################################################
# START OF VIEW CONVERSATION
async def view_farm_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "chose view farms")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await context.bot.send_message(
            chat_id=user.id,
            text="Choose one of your farms",
            reply_markup=farms_list_reply(db, user.id),
        )
        return VIEW_FARM
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text="You have not registered any garden yet",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END

async def view_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    farm = update.message.text
    # farm = f"view{farm}"
    user = update.effective_user
    user_farms = db.get_farms(user.id)
    user_farms_names = list(db.get_farms(user.id).keys())
    if farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("The previous opeation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if farm not in user_farms_names and farm != "↩️ back":
        db.log_activity(user.id, "error - chose wrong farm to view", farm)
        await context.bot.send_message(
            chat_id=user.id,
            text="Choose one of your farms",
            reply_markup=farms_list_reply(db, user.id),
        )
        return VIEW_FARM
    if farm == "↩️ back":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id, text="The operation was cancelled!", reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    if not user_farms[farm].get("location") == {}:
        latitude = user_farms[farm].get("location").get("latitude")
        longitude = user_farms[farm].get("location").get("longitude")
    else:
        latitude = None
        longitude = None
    message_id = update.effective_message.message_id
    try:
        text = f"""
<b>{farm}</b>
the crop: {user_farms[farm].get("product")}
the area: {user_farms[farm].get("area")}
the chosen address ⬇️
"""
        await context.bot.send_message(chat_id=user.id, text=text, parse_mode=ParseMode.HTML)
        if latitude and longitude:
            await context.bot.send_location(
                chat_id=user.id,
                latitude=latitude,
                longitude=longitude,
                reply_markup=farms_list_reply(db, user.id),
            )
        else:
            await context.bot.send_message(
                chat_id=user.id,
                text=f"Unfortunately the location of <{farm}> has not been registered. "
                "You can register your location using the 'edit farm' option.",
                reply_markup=farms_list_reply(db, user.id),
            )
        db.log_activity(user.id, "viewed a farm", farm)
    except KeyError:
        logger.info(f"key {farm} doesn't exist.")
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The operation was cancelled!")
    return ConversationHandler.END

view_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("🖼 see the farms"), view_farm_keyboard)],
        states={
            VIEW_FARM: [MessageHandler(filters.ALL, view_farm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )