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
    conf_del_keyboard,
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
CONFIRM_DELETE, DELETE_FARM = range(2)
MENU_CMDS = ['✍ sign up', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()

# START OF DELETE CONVERSATION
async def delete_farm_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start delete process")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await update.message.reply_text(
            "Choose one of your farms",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    else:
        await update.message.reply_text(
            "You have not registered any garden yet", reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END

async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    farm = update.message.text
    user_data["farm_to_delete"] = farm
    user = update.effective_user
    user_farms = db.get_farms(user.id)
    user_farms_names = list(db.get_farms(user.id).keys())
    if farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if farm not in user_farms_names and farm != "↩️ back":
        db.log_activity(user.id, "error - wrong farm to delete", farm)
        await context.bot.send_message(
            chat_id=user.id,
            text="Choose one of your farms",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    if farm == "↩️ back":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id, text="The operation was cancelled!", reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm to delete", farm)
    location = user_farms.get(farm)["location"]
    text = f"""Are you sure you want to delete <b>{farm}</b> with the following specifications?
Crop: {user_farms[farm].get("product")}
Area: {user_farms[farm].get("area")}
Selected address ⬇️
"""
    await context.bot.send_message(chat_id=user.id, text=text, parse_mode=ParseMode.HTML)

    if location and location != {"latitude": None, "longitude": None}:
        await context.bot.send_location(
            chat_id=user.id,
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            reply_markup=conf_del_keyboard(),
        )
        return DELETE_FARM
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text=f"location of <{farm}> is not registered. ",
            reply_markup=conf_del_keyboard(),
        )
        return DELETE_FARM

async def delete_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    farm = user_data["farm_to_delete"]
    answer = update.message.text
    acceptable = ["yes", "no", "back"]
    if answer not in acceptable:
        db.log_activity(user.id, "error - wrong delete confirmation", answer)
        await context.bot.send_message(
            chat_id=user.id, text="The operation was not successful", reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif answer == "back":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id,
            text="Choose one of your farms",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    elif answer == "no":
        db.log_activity(user.id, "stopped delete")
        await context.bot.send_message(
            chat_id=user.id, text="The operation was cancelled", reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif answer == "yes":
        db.log_activity(user.id, "confirmed delete")
        try:
            db.user_collection.update_one(
                {"_id": user.id}, {"$unset": {f"farms.{farm}": ""}}
            )
            text = f"{farm} was successfully deleted."
            await context.bot.send_message(
                chat_id=user.id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=db.find_start_keyboard(user.id),
            )
            return ConversationHandler.END
        except KeyError:
            logger.info(f"DELETE: key {farm} doesn't exist for user {user.id}.")
            return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The operation was cancelled!")
    return ConversationHandler.END


delete_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("🗑 delete the farm"), delete_farm_keyboard)
        ],
        states={
            CONFIRM_DELETE: [MessageHandler(filters.ALL, confirm_delete)],
            DELETE_FARM: [MessageHandler(filters.ALL, delete_farm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )