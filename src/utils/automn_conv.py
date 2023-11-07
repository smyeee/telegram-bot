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
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()

# START OF AUTOMN TIME CONVERSATION
async def automn_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "request pre harvest")
    if db.check_if_user_has_pesteh(user.id):
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id, True),
        )
        return AUTOMN_MONTH
    else:
        db.log_activity(user.id, "error - no pesteh farms to set automn time")
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغ پسته‌ای ثبت نکرده اید",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END

async def ask_automn_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    
    if farm == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await update.message.reply_text("عملیات لغو شد", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for harvest advice" , farm)
        await update.message.reply_text("لطفا دوباره تلاش کنید. نام باغ اشتباه بود", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    
    db.log_activity(user.id, f"chose farm for setting automn time", farm)
    if user_farms[farm].get("automn-time"):
        reply_text = "نیاز سرمایی شما در حال محاسبه است و در زمان لازم اطلاع‌رسانی خواهد شد."
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        user_data["set-automn-time-of-farm"] = farm
        reply_text = "برای محاسبه نیاز سرمایی لطفا زمان خزان باغ خود را ثبت کنید."
        await update.message.reply_text(reply_text, reply_markup=automn_month())
        return AUTOMN_WEEK
    
async def ask_automn_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    month = update.message.text
    acceptable_months = ["آبان", "آذر"]
    if month == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id, True),
        )
        return AUTOMN_MONTH
    elif month in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", month)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif month not in acceptable_months:
        db.log_activity(user.id, "error - chose wrong month for automn time" , month)
        await update.message.reply_text("لطفا دوباره تلاش کنید. ماه انتخاب شده اشتباه بود.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose month for automn time" , month)
    user_data["automn-month"] = month
    reply_text = "هفته خزان باغ خود را انتخاب کنید."
    await update.message.reply_text(reply_text, reply_markup=automn_week())
    return SET_AUTOMN_TIME

async def set_automn_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    week = update.message.text
    acceptable_weeks = ['هفته دوم', 'هفته اول', 'هفته چهارم', 'هفته سوم']
    if week == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        reply_text = "برای محاسبه نیاز سرمایی لطفا زمان خزان باغ خود را ثبت کنید."
        await update.message.reply_text(reply_text, reply_markup=automn_month())
        return AUTOMN_WEEK
    elif week in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", week)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif week not in acceptable_weeks:
        db.log_activity(user.id, "error - chose wrong week for automn time" , week)
        await update.message.reply_text("لطفا دوباره تلاش کنید. هفته انتخاب شده اشتباه بود", reply_markup=db.find_start_keyboard(user.id))
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
رقم ثبت شده برای باغ پسته شما <b>{product}</b> است. 
در صورت صحیح بودن <b>/finish</b> را بزنید. در غیر این صورت رقم‌های پسته خود را انتخاب کنید.
همچنین می‌توانید رقم پسته را در صورتی که در لیست موجود نبود بنویسید.
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
    if new_product == 'بازگشت':
        db.log_activity(user.id, "back")
        reply_text = "هفته خزان باغ خود را انتخاب کنید."
        await update.message.reply_text(reply_text, reply_markup=automn_week())
        return SET_AUTOMN_TIME
    elif new_product == '/finish':
        db.log_activity(user.id, "finished adding products for farm during set-automn-time")
        reply_text = "از ثبت زمان خزان باغ متشکریم، نیاز سرمایی مخصوص رقم باغ شما محاسبه شده و از همین جا قابل مشاهده خواهد بود."
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        db.log_activity(user.id, "added product for farm during set-automn-time")
        db.set_user_attribute(user.id, f"farms.{farm}.product", f"{product} - {new_product}")
        farm_dict = db.get_farms(user.id)[farm]
        product = farm_dict.get("product")
        reply_text = f"""
    رقم ثبت شده برای باغ پسته شما <b>{product}</b> است. 
    در صورت صحیح بودن <b>/finish</b> را بزنید. در غیر این صورت رقم‌های پسته خود را انتخاب کنید.
    همچنین می‌توانید رقم پسته را در صورتی که در لیست موجود نبود بنویسید.
        """
        await update.message.reply_text(reply_text, reply_markup=get_product_keyboard(), parse_mode=ParseMode.HTML)
        return CONFIRM_PRODUCT
    
    
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END   


automn_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^❄️ نیاز سرمایی$'), automn_time)],
        states={
            AUTOMN_MONTH: [MessageHandler(filters.TEXT , ask_automn_month)],
            AUTOMN_WEEK: [MessageHandler(filters.TEXT , ask_automn_week)],
            SET_AUTOMN_TIME: [MessageHandler(filters.TEXT , set_automn_time)],
            CONFIRM_PRODUCT: [MessageHandler(filters.TEXT | filters.COMMAND , confirm_product)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
