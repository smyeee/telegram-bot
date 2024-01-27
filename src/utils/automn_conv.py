from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.error import Forbidden, BadRequest
from telegram.constants import ParseMode

import datetime
import jdatetime
import warnings

import database

from .logger import logger
from .keyboards import (
    farms_list_reply,
    automn_month,
    automn_week,
    get_product_keyboard
)

warnings.filterwarnings("ignore", category=UserWarning)

AUTOMN_MONTH, AUTOMN_WEEK, SET_AUTOMN_TIME, CONFIRM_PRODUCT = range(4)
MENU_CMDS = ['✍ sign up', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()

# START OF AUTOMN TIME CONVERSATION
async def automn_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start to set automn time")
    if db.check_if_user_has_pesteh(user.id):
        await context.bot.send_message(
            chat_id=user.id,
            text="Choose one of your gardens",
            reply_markup=farms_list_reply(db, user.id, True),
        )
        return AUTOMN_MONTH
    else:
        db.log_activity(user.id, "error - no pesteh farms to set automn time")
        await context.bot.send_message(
            chat_id=user.id,
            text="You have not registered any Pistachio garden yet",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END

async def ask_automn_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    
    if farm == '↩️ back':
        db.log_activity(user.id, "back")
        await update.message.reply_text("The operation was cancelled", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for automn time" , farm)
        await update.message.reply_text("Please try again. the garden's name was wrong.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    
    db.log_activity(user.id, f"chose farm for setting automn time", farm)
    if user_farms[farm].get("automn-time"):
        db.log_activity(user.id, "automn time of farm was already set", farm)
        reply_text = "Your cooling requirement is being calculated and will be notified when necessary."
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        user_data["set-automn-time-of-farm"] = farm
        reply_text = "To calculate the cooling requirement, please record the fall time of your garden."
        await update.message.reply_text(reply_text, reply_markup=automn_month())
        return AUTOMN_WEEK
    
async def ask_automn_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    month = update.message.text
    acceptable_months = ["Aban", "Azar"]
    if month == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id,
            text="Choose one of your gardens",
            reply_markup=farms_list_reply(db, user.id, True),
        )
        return AUTOMN_MONTH
    elif month in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", month)
        await update.message.reply_text("The previous operation was cancelled. Please again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif month not in acceptable_months:
        db.log_activity(user.id, "error - chose wrong month for automn time" , month)
        await update.message.reply_text("Please try again. The chosen month was wrong.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose month for automn time" , month)
    user_data["automn-month"] = month
    reply_text = "choose the autumn week of your garden."
    await update.message.reply_text(reply_text, reply_markup=automn_week())
    return SET_AUTOMN_TIME

async def set_automn_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    week = update.message.text
    acceptable_weeks = ['the second week', 'the first week', 'the forth week', 'the third week']
    if week == '↩️ back':
        db.log_activity(user.id, "back")
        reply_text = "To calculate the cooling requirement, please record the fall time of your garden."
        await update.message.reply_text(reply_text, reply_markup=automn_month())
        return AUTOMN_WEEK
    elif week in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", week)
        await update.message.reply_text("The previous opration was cancelled please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif week not in acceptable_weeks:
        db.log_activity(user.id, "error - chose wrong week for automn time" , week)
        await update.message.reply_text("Please try again. The chosen week was invalid", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose week for automn time" , week)
    user_data["automn-week"] = week
    month = user_data["automn-month"]
    farm = user_data["set-automn-time-of-farm"]
    logger.info(f"farm: {farm}")
    db.set_user_attribute(user.id, f"farms.{farm}.automn-time", f"{week} - {month}")
    farm_dict = db.get_farms(user.id)[farm]
    product = farm_dict.get("product")
    reply_text = f"""
The cultivar registered for your pistachio garden is <b>{product}</b>.
If it is correct, press <b>/finish</b>. Otherwise, choose your own pistachio numbers.
You can also write the pistachio number if it is not in the list.
    """
    await update.message.reply_text(reply_text, reply_markup=get_product_keyboard(), parse_mode=ParseMode.HTML)
    return CONFIRM_PRODUCT

async def confirm_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    farm = user_data["set-automn-time-of-farm"]
    farm_dict = db.get_farms(user.id)[farm]
    product = farm_dict.get("product")
    new_product = update.message.text
    if new_product == 'back':
        db.log_activity(user.id, "back")
        reply_text = "Choose the autumn week of your garden."
        await update.message.reply_text(reply_text, reply_markup=automn_week())
        return SET_AUTOMN_TIME
    elif new_product == '/finish':
        db.log_activity(user.id, "finished adding products for farm during set-automn-time")
        reply_text = "Thank you for recording the time of fall in the garden, the cold requirement for your garden variety has been calculated and can be seen from here."
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        db.log_activity(user.id, "added product for farm during set-automn-time", new_product)
        db.set_user_attribute(user.id, f"farms.{farm}.product", f"{product} - {new_product}")
        farm_dict = db.get_farms(user.id)[farm]
        product = farm_dict.get("product")
        reply_text = f"""
The cultivar registered for your pistachio garden is <b>{product}</b>.
If it is correct, press <b>/finish</b>. Otherwise, choose your own pistachio numbers.
You can also write the pistachio number if it is not in the list.
        """
        await update.message.reply_text(reply_text, reply_markup=get_product_keyboard(), parse_mode=ParseMode.HTML)
        return CONFIRM_PRODUCT
    
    
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The operaton was cancelled!")
    return ConversationHandler.END   


automn_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^❄️ cold demand$'), automn_time)],
        states={
            AUTOMN_MONTH: [MessageHandler(filters.TEXT , ask_automn_month)],
            AUTOMN_WEEK: [MessageHandler(filters.TEXT , ask_automn_week)],
            SET_AUTOMN_TIME: [MessageHandler(filters.TEXT , set_automn_time)],
            CONFIRM_PRODUCT: [MessageHandler(filters.TEXT | filters.COMMAND , confirm_product)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
