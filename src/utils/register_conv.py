from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from telegram.constants import ParseMode

import datetime

import database

from .logger import logger
from .sms_funcs import sms_no_farm
# Constants for ConversationHandler states
ASK_PHONE, HANDLE_PHONE = range(2)
MENU_CMDS = ['✍ sign up', '📤 invite others', '🖼see the farms', '➕ add farm', '🗑 delete farm', '✏️ edit farms', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()


# START OF REGISTER CONVERSATION
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start register", f"{user.id} - username: {user.username}")
    if db.check_if_user_is_registered(user_id=user.id):
        await update.message.reply_text(
            "You have already signed up. You can register your gardens using /start "
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "Please enter your name and your family name \n /cancel", reply_markup=ReplyKeyboardRemove()
    )
    return ASK_PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "entered name", f"{update.message.text}")
    user_data = context.user_data
    # Get the answer to the area question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not update.message.text:
        await update.message.reply_text("Please enter your name and your family name \n /cancel")
        db.log_activity(user.id, "error - enter name", f"{update.message.text}")
        return ASK_PHONE
    name = update.message.text.strip()
    user_data["name"] = name
    db.set_user_attribute(user_id=user.id, key="name", value=name)
    await update.message.reply_text("Please enter your phone number: \n /cancel")
    return HANDLE_PHONE

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    # Get the answer to the area question
    phone = update.message.text
    if phone in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", phone)
        await update.message.reply_text("The previous operation was cancelled. Please try again", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not phone or not phone.isdigit() or len(phone) != 11:
        db.log_activity(user.id, "error - entered phone", phone)
        await update.message.reply_text("The number is not valid. Please try again:. \n /cancel")
        return HANDLE_PHONE
    db.log_activity(user.id, "entered phone", phone)
    user_data["phone"] = phone
    db.set_user_attribute(user_id=user.id, key="phone-number", value=phone)
    reply_text = """
You can register your gardens using <b>('➕ add farm')</b>.
    """
    keyboard = [['➕ add farm']]
    
    await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True))
    if datetime.time(2, 30).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(17, 30).strftime("%H%M"): 
        context.job_queue.run_once(sms_no_farm, when=datetime.timedelta(hours=2), chat_id=user.id, data=user.username)
    else:
        context.job_queue.run_once(sms_no_farm, when=datetime.time(4, 30), chat_id=user.id, data=user.username) 
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The operation was cancelled!")
    return ConversationHandler.END


register_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('✍ sign up'), register)],
        states={
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            HANDLE_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )