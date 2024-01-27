import datetime
import jdatetime
from telegram import (
    Update,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters
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
    start_keyboard_no_farms,
    start_keyboard_no_location,
    start_keyboard_not_pesteh,
    start_keyboard_pesteh_kar,
    view_sp_advise_keyboard,
    view_advise_keyboard,
    farms_list_reply
)
from .logger import logger



# Constants for ConversationHandler states
HANDLE_INV_LINK = 0
HARVEST_OFF = 0
HARVEST_ON = 0
MENU_CMDS = ['✍ sign up', '📤 invite others', '🖼 visit the farms', '➕ add farm', '🗑 delete farm', '✏️ edit the farms', '🌦 ask for meteorological information', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()
###################################################################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    context.job_queue.run_once(no_farm_reminder, when=datetime.timedelta(hours=1), chat_id=user.id, data=user.username)    
    user_document = db.user_collection.find_one( { "_id": user.id } )
    # Check if the user has already signed up
    if not db.check_if_user_is_registered(user_id=user.id):
        user_data["username"] = user.username
        user_data["blocked"] = False
        first_seen = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        db.add_new_user(user_id=user.id, username=user.username, first_seen=first_seen)
        logger.info(f"{user.username} (id: {user.id}) started the bot.")
        reply_text = """
Hi dear gardener!
Thanks for trusting us.
To receive practical meteorological advices, including frostbite, sunstroke and sun burn, damage, coldness need, etc... complete your sign up and then register your gardens.
contact us:
admin: @agriiadmin
Landline phone: 02164063410
                """
        args = context.args
        if args:
            db.log_token_use(user.id, args[0])
        await update.message.reply_text(reply_text, reply_markup=register_keyboard())
        await update.message.reply_text("https://t.me/agriweath/48")
        context.job_queue.run_once(register_reminder, when=datetime.timedelta(hours=3), chat_id=user.id, data=user.username)    
        return ConversationHandler.END
    else:
#         reply_text = """
# باغدار عزیز سلام
# از این که به ما اعتماد کردید متشکریم.
# برای دریافت توصیه‌های کاربردی هواشناسی از قبیل سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، نیاز سرمایی و … باغ های خد را در بات ثبت کنید.
# راه‌های ارتباطی با ما:
# ادمین: @agriiadmin
# تلفن ثابت: 02164063410
#                 """
#         await update.message.reply_text(reply_text, reply_markup=start_keyboard())
        if not db.check_if_user_has_farms(user.id, user_document):
            reply_text = "Please register your farm before accessing Abad's services"
            await update.message.reply_text(reply_text,
                                            reply_markup=start_keyboard_no_farms())
            
        else:
            if not db.check_if_user_has_farms_with_location(user.id, user_document):
                reply_text = "Please register your farm's location before accessing Abad's services"
                await update.message.reply_text(reply_text,
                                                reply_markup=start_keyboard_no_location())
            else:
                if not db.check_if_user_has_pesteh(user.id, user_document):
                    reply_text = "Welcome to Abad!"
                    await update.message.reply_text(reply_text,
                                                    reply_markup=start_keyboard_not_pesteh())
                else:
                    reply_text = "Welcome to Abad!"
                    await update.message.reply_text(reply_text,
                                                    reply_markup=start_keyboard_pesteh_kar())

async def user_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text("Your keyboard is:", reply_markup=db.find_start_keyboard(user.id))

# CREATE PERSONALIZED INVITE LINK FOR A USER
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "chose invite-link menu option")
    random_string = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
    db.set_user_attribute(user.id, "invite-links", random_string, array=True)
    db.add_token(user.id, random_string)
    link = f"https://t.me/agriweathbot?start={random_string}"
    await update.message.reply_text(f"""
Hey guys!
There is a robot that sends you meteorological advices according to your garden's location and number of crop.
I highly recommend you to use it.
                                        
{link}
""", reply_markup=db.find_start_keyboard(user.id))

# invite link generation with a conversation, not added to app handlers right now.
async def invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "chose invite-link menu option")
    keyboard = [['see the previous links'], ['Create new invite link'], ['back']]
    await update.message.reply_text("Please choose:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))
    return HANDLE_INV_LINK

async def handle_invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    if message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif message_text=="back":
        db.log_activity(user.id, "back")
        await update.message.reply_text("The previous operation was cancelled.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif message_text=="see th previous links":
        db.log_activity(user.id, "chose to view previous links")
        links = db.get_user_attribute(user.id, "invite-links")
        if links:
            await update.message.reply_text(links, reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        else:
            await update.message.reply_text("You have not made the invite link yet.", reply_markup=db.find_start_keyboard(user.id))
            ConversationHandler.END
    elif message_text=="Creat new invite link":
        db.log_activity(user.id, "chose to create an invite-link")
        random_string = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
        db.set_user_attribute(user.id, "invite-links", random_string, array=True)
        db.add_token(user.id, random_string)
        link = f"https://t.me/agriweathbot?start={random_string}"
        await update.message.reply_text(f"""
Hey guys!
There is a robot that sends you meteorological advices according to your garden's location and number of crop.
I highly recommend you to use it.
                                        
{link}
""",    
            reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else: 
        db.log_activity(user.id, "error - option not valid", message_text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END



async def change_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    jdate = jdatetime.datetime.now().strftime("%Y/%m/%d")
    jday2 = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    jday3 = (jdatetime.datetime.now() + jdatetime.timedelta(days=2)).strftime("%Y/%m/%d")
    try:
        await query.answer()
    except BadRequest:
        logger.error(f"query.answer() caused BadRequest error. user: {query.message.chat.id}")
    user_id = query.message.chat.id
    # logger.info(f"data:{query.data}, user: {user_id}\n---------")
    farm_name = query.data.split("\n")[0]
    day_chosen = query.data.split("\n")[1]
    advise_3days = db.user_collection.find_one({"_id": user_id})["farms"][farm_name].get("advise")
    advise_sp_3days = db.user_collection.find_one({"_id": user_id})["farms"][farm_name].get("sp-advise")
    if day_chosen=="today_advise":
        day = "امروز"
        if not advise_3days:
            return
        advise = advise_3days["today"]
        keyboard = view_advise_keyboard(farm_name)
        if pd.isna(advise):
            advise = "There is no advice for this date"
        date = jdate
        db.log_activity(user_id, "chose advice date", "day1")
    elif day_chosen=="day2_advise":
        day = "فردا"
        if not advise_3days:
            return
        advise = advise_3days["day2"]
        keyboard = view_advise_keyboard(farm_name)
        if pd.isna(advise):
            advise = "There is no advice for this date"
        date = jday2
        db.log_activity(user_id, "chose advice date", "day2")
    elif day_chosen=="day3_advise":
        day = "پس‌فردا"
        if not advise_3days:
            return
        advise = advise_3days["day3"]
        keyboard = view_advise_keyboard(farm_name)
        if pd.isna(advise):
            advise = "There is no advice for this date"
        date = jday3
        db.log_activity(user_id, "chose advice date", "day3")
    elif day_chosen=="today_sp_advise":
        day = "امروز"
        if not advise_sp_3days:
            return
        advise = advise_sp_3days["today"]
        keyboard = view_sp_advise_keyboard(farm_name)
        if pd.isna(advise):
            advise = "There is no advice for this date"
        date = jdate
        db.log_activity(user_id, "chose sp-advice date", "day1")
    elif day_chosen=="day2_sp_advise":
        day = "فردا"
        if not advise_sp_3days:
            return
        advise = advise_sp_3days["day2"]
        keyboard = view_sp_advise_keyboard(farm_name)
        if pd.isna(advise):
            advise = "There is no advice for this date"
        date = jday2
        db.log_activity(user_id, "chose sp-advice date", "day2")
    elif day_chosen=="day3_sp_advise":
        day = "پس‌فردا"
        if not advise_sp_3days:
            return
        advise = advise_sp_3days["day3"]
        keyboard = view_sp_advise_keyboard(farm_name)
        if pd.isna(advise):
            advise = "There is no advice for this date"
        date = jday3
        db.log_activity(user_id, "chose sp-advice date", "day3")
    
    advise = f"""
The harvest advice for your garden called <b>#{farm_name.replace(" ", "_")}</b> for #{day} date <b>{date}</b>:

<pre>{advise}</pre>
"""
    try:
        await query.edit_message_text(advise, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        db.log_activity(user_id, "received advice for other date")
    except Forbidden or BadRequest:
        logger.info("encountered error trying to respond to CallbackQueryHandler")
        db.log_activity(user_id, "error - couldn't receive advice for other date")
    except:
        logger.info("Unexpected error") # Could be message not modified?
        db.log_activity(user_id, "error - couldn't receive advice for other date")

async def ask_harvest_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "harvest_off")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await context.bot.send_message(
            chat_id=user.id,
            text="Choose one of your gardens.",
            reply_markup=farms_list_reply(db, user.id),
        )
        return HARVEST_OFF
    else:
        db.log_activity(user.id, "error - no farm for harvest_off")
        await context.bot.send_message(
            chat_id=user.id,
            text="You have not registered any garden yet",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END
    
async def harvest_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    if farm == '↩️ back':
        db.log_activity(user.id, "back")
        await update.message.reply_text("The operation was cancelled", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for harvest_off" , farm)
        await update.message.reply_text("Please try again. The garden's name was incorrect", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("The previous operaion was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm for harvest_off", farm)
    db.set_user_attribute(user.id, f"farms.{farm}.harvest-off", True)
    reply_text = f"""
Sending harvest advices for the garden <b>#{farm.replace(" ", "_")}</b> was stopped. 
Incase your interested in receiving harvest advices again. press /harvest_on.
"""
    await context.bot.send_message(chat_id=user.id, text= reply_text, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def ask_harvest_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "harvest_on")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await context.bot.send_message(
            chat_id=user.id,
            text="Choose one of your gardens",
            reply_markup=farms_list_reply(db, user.id),
        )
        return HARVEST_ON
    else:
        db.log_activity(user.id, "error - no farm for harvest_on")
        await context.bot.send_message(
            chat_id=user.id,
            text="You have not registered any garden yet",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END
    
async def harvest_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    if farm == '↩️ back':
        db.log_activity(user.id, "back")
        await update.message.reply_text("The operation was cancelled", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for harvest_on" , farm)
        await update.message.reply_text("Please try again. The garden's name was incorrect", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm for harvest_on", farm)
    db.set_user_attribute(user.id, f"farms.{farm}.harvest-off", False)
    reply_text = f"""
harvest advices will be sent for the <b>#{farm.replace(" ", "_")}</b> garden.
"""
    await context.bot.send_message(chat_id=user.id, text= reply_text, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The operation was cancelled!")
    return ConversationHandler.END

harvest_off_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("harvest_off", ask_harvest_off)],
        states={
            HARVEST_OFF: [MessageHandler(filters.ALL, harvest_off)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

harvest_on_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("harvest_on", ask_harvest_on)],
        states={
            HARVEST_ON: [MessageHandler(filters.ALL, harvest_on)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
 
invite_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📤 invite others"), invite_link)],
        states={
            HANDLE_INV_LINK: [MessageHandler(filters.TEXT , handle_invite_link)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )