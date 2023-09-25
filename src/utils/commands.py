import datetime
import jdatetime
from telegram import (
    Update,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest
import pandas as pd
import random
import string

import database
from .regular_jobs import register_reminder, no_farm_reminder
from .keyboards import (
    register_keyboard,
    start_keyboard,
    view_advise_keyboard
)
from .logger import logger



# Constants for ConversationHandler states
HANDLE_INV_LINK = 0
ADMIN_LIST = [103465015, 31583686, 391763080, 216033407, 5827206050]
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده باغ ها', '➕ اضافه کردن باغ', '🗑 حذف باغ ها', '✏️ ویرایش باغ ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
###################################################################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    context.job_queue.run_once(no_farm_reminder, when=datetime.timedelta(hours=1), chat_id=user.id, data=user.username)    
    # Check if the user has already signed up
    if not db.check_if_user_is_registered(user_id=user.id):
        user_data["username"] = user.username
        user_data["blocked"] = False
        first_seen = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        db.add_new_user(user_id=user.id, username=user.username, first_seen=first_seen)
        logger.info(f"{user.username} (id: {user.id}) started the bot.")
        reply_text = """
باغدار عزیز سلام
از این که به ما اعتماد کردید متشکریم.
برای دریافت توصیه‌های کاربردی هواشناسی از قبیل سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، نیاز سرمایی و … ابتدا ثبت نام خود را کامل کرده
و سپس باغ های خود را ثبت کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
تلفن ثابت: 02164063410
                """
        args = context.args
        if args:
            db.log_token_use(user.id, args[0])
        await update.message.reply_text(reply_text, reply_markup=register_keyboard())
        await update.message.reply_text("https://t.me/agriweath/48")
        context.job_queue.run_once(register_reminder, when=datetime.timedelta(hours=3), chat_id=user.id, data=user.username)    
        return ConversationHandler.END
    else:
        reply_text = """
باغدار عزیز سلام
از این که به ما اعتماد کردید متشکریم.
برای دریافت توصیه‌های کاربردی هواشناسی از قبیل سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، نیاز سرمایی و … باغ های خد را در بات ثبت کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
تلفن ثابت: 02164063410
                """
        await update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END



# CREATE PERSONALIZED INVITE LINK FOR A USER
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "chose invite-link menu option")
    random_string = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
    db.set_user_attribute(user.id, "invite-links", random_string, array=True)
    db.add_token(user.id, random_string)
    link = f"https://t.me/agriweathbot?start={random_string}"
    await update.message.reply_text(f"""
سلام دوستان
یک ربات هست که با توجه به موقعیت باغ شما و رقم محصول، توصیه‌های هواشناسی براتون ارسال میکنه
پیشنهاد میکنم حتما ازش استفاده کنید.
                                        
{link}
""", reply_markup=start_keyboard())

# invite link generation with a conversation, not added to app handlers right now.
async def invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "chose invite-link menu option")
    keyboard = [['مشاهده لینک های قبلی'], ['ایجاد لینک دعوت جدید'], ['بازگشت']]
    await update.message.reply_text("لطفا انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))
    return HANDLE_INV_LINK

async def handle_invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    if message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text=="بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("عمیلات قبلی لغو شد.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text=="مشاهده لینک های قبلی":
        db.log_activity(user.id, "chose to view previous links")
        links = db.get_user_attribute(user.id, "invite-links")
        if links:
            await update.message.reply_text(links, reply_markup=start_keyboard())
            return ConversationHandler.END
        else:
            await update.message.reply_text("شما هنوز لینک دعوت نساخته‌اید.", reply_markup=start_keyboard())
            ConversationHandler.END
    elif message_text=="ایجاد لینک دعوت جدید":
        random_string = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5))
        db.set_user_attribute(user.id, "invite-links", random_string, array=True)
        link = f"https://t.me/agriweathbot?start={random_string}"
        await update.message.reply_text(f"""
سلام دوستان
یک ربات هست که با توجه به موقعیت باغ شما و رقم محصول آن، توصیه‌های هواشناسی براتون ارسال میکنه
پیشنهاد میکنم حتما ازش استفاده کنید.
                                        
{link}
""",    
            reply_markup=start_keyboard())
        return ConversationHandler.END
    else: 
        db.log_activity(user.id, "error - option not valid", message_text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END


# invite_conv = ConversationHandler(
    #     entry_points=[MessageHandler(filters.Regex("دعوت از دیگران"), invite_link)],
    #     states={
    #         HANDLE_INV_LINK: [MessageHandler(filters.TEXT , handle_invite_link)]
    #     },
    #     fallbacks=[CommandHandler("cancel", cancel)],
    # )

async def change_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    jdate = jdatetime.datetime.now().strftime("%Y/%m/%d")
    jday2 = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    jday3 = (jdatetime.datetime.now() + jdatetime.timedelta(days=2)).strftime("%Y/%m/%d")
    await query.answer()
    user_id = query.message.chat.id
    # logger.info(f"data:{query.data}, user: {user_id}\n---------")
    farm_name = query.data.split("\n")[0]
    day_chosen = query.data.split("\n")[1]
    advise_3days = db.user_collection.find_one({"_id": user_id})["farms"][farm_name].get("advise")
    advise_sp_3days = db.user_collection.find_one({"_id": user_id})["farms"][farm_name].get("sp-advise")
    if day_chosen=="today_advise":
        advise = advise_3days["today"]
        if pd.isna(advise):
            advise = "توصیه‌ای برای این تاریخ موجود نیست"
        date = jdate
        db.log_activity(user_id, "chose advice date", "day1")
    elif day_chosen=="day2_advise":
        advise = advise_3days["day2"]
        if pd.isna(advise):
            advise = "توصیه‌ای برای این تاریخ موجود نیست"
        date = jday2
        db.log_activity(user_id, "chose advice date", "day2")
    elif day_chosen=="day3_advise":
        advise = advise_3days["day3"]
        if pd.isna(advise):
            advise = "توصیه‌ای برای این تاریخ موجود نیست"
        date = jday3
        db.log_activity(user_id, "chose advice date", "day3")
    elif day_chosen=="today_sp_advise":
        advise = advise_sp_3days["today"]
        if pd.isna(advise):
            advise = "توصیه‌ای برای این تاریخ موجود نیست"
        date = jdate
        db.log_activity(user_id, "chose sp-advice date", "day1")
    elif day_chosen=="day2_sp_advise":
        advise = advise_sp_3days["day2"]
        if pd.isna(advise):
            advise = "توصیه‌ای برای این تاریخ موجود نیست"
        date = jday2
        db.log_activity(user_id, "chose sp-advice date", "day2")
    elif day_chosen=="day3_sp_advise":
        advise = advise_sp_3days["day3"]
        if pd.isna(advise):
            advise = "توصیه‌ای برای این تاریخ موجود نیست"
        date = jday3
        db.log_activity(user_id, "chose sp-advice date", "day3")
    
    advise = f"""
توصیه مرتبط با وضعیت آب و هوایی باغ شما با نام <b>#{farm_name.replace(" ", "_")}</b> مورخ <b>{date}</b>:

<pre>{advise}</pre>
"""
    try:
        await query.edit_message_text(advise, reply_markup=view_advise_keyboard(farm_name), parse_mode=ParseMode.HTML)
        db.log_activity(user_id, "received advice for other date")
    except Forbidden or BadRequest:
        logger.info("encountered error trying to respond to CallbackQueryHandler")
        db.log_activity(user_id, "error - couldn't receive advice for other date")
    except:
        logger.info("Unexpected error") # Could be message not modified?
        db.log_activity(user_id, "error - couldn't receive advice for other date")