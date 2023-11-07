import datetime
import jdatetime
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.error import Forbidden, BadRequest

import os
from fiona.errors import DriverError
import warnings
import database
from .logger import logger
from .keyboards import (
    farms_list_reply,
    view_advise_keyboard
)
from .table_generator import table
from telegram.constants import ParseMode

warnings.filterwarnings("ignore", category=UserWarning)

RECV_HARVEST, RECV_PRE_HARVEST, RECV_POST_HARVEST = range(3)
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()

# START OF REQUEST WEATHER CONVERSATION
async def req_pre_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    db.log_activity(user.id, "request pre harvest")
    if db.check_if_user_has_pesteh(user.id):
        user_data["harvest_data"] = "PRE"
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id, True),
        )
        return RECV_HARVEST
    else:
        db.log_activity(user.id, "error - no farm for pre harvest advise")
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغ پسته‌ای ثبت نکرده اید",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END
    
async def req_post_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    db.log_activity(user.id, "request post harvest")
    if db.check_if_user_has_pesteh(user.id):
        user_data["harvest_data"] = "POST"
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id, True),
        )
        return RECV_HARVEST
    else:
        db.log_activity(user.id, "error - no farm for post harvest advise")
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغ پسته‌ای ثبت نکرده اید",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END
    
async def recv_harvest_advice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    harvest_type = user_data.get("harvest_data", "")
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
    db.log_activity(user.id, f"chose farm for {harvest_type} harvest advice", farm)
    longitude = user_farms[farm]["location"]["longitude"]
    latitude = user_farms[farm]["location"]["latitude"]
    if user_farms[farm].get("link-status") == "To be verified":
        reply_text = "لینک لوکیشن ارسال شده توسط شما هنوز تایید نشده است.\nلطفا تا بررسی ادمین آباد شکیبا باشید."
        await context.bot.send_message(chat_id=user.id, text=reply_text,reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not longitude:
        await context.bot.send_message(chat_id=user.id, text="موقعیت باغ شما ثبت نشده است. لظفا پیش از درخواست توصیه برداشت نسبت به ثبت موقعیت باغ خود اقدام فرمایید.",
                                 reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    today = datetime.datetime.now().strftime("%Y%m%d")
    day2 = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
    day3 = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y%m%d")
    jtoday = jdatetime.datetime.now().strftime("%Y/%m/%d")
    jday2 = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    jday3 = (jdatetime.datetime.now() + jdatetime.timedelta(days=2)).strftime("%Y/%m/%d")
    
    # today = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    # jtoday = (jdatetime.datetime.now() - jdatetime.timedelta(days=1)).strftime("%Y%m%d")
    # day2 = datetime.datetime.now().strftime("%Y%m%d")
    # day3 = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
    # jday2 = jdatetime.datetime.now().strftime("%Y/%m/%d")
    # jday3 = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    # jday3 = (jdatetime.datetime.now() + jdatetime.timedelta(days=2)).strftime("%Y/%m/%d")
    
    jdates = [jtoday, jday2, jday3]
    advise_tags = ['امروز', 'فردا', 'پس فردا']
    try:
        if datetime.time(7, 0).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(20, 30).strftime("%H%M"): 
            if harvest_type == "PRE":
                harvest_data = gpd.read_file(f"data/pesteh{today}_Advise_Bef.geojson")
                advice = "پیش از برداشت"
            elif harvest_type == "POST":
                harvest_data = gpd.read_file(f"data/pesteh{today}_Advise_Aft.geojson")
                advice = "پس از برداشت"
            else:
                db.log_activity(user.id, "error - harvest type not found", harvest_type)
                await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
                return ConversationHandler.END
        else:
            if harvest_type == "PRE":
                harvest_data = gpd.read_file(f"data/pesteh{yesterday}_Advise_Bef.geojson")
                advice = "پیش از برداشت"
            elif harvest_type == "POST":
                harvest_data = gpd.read_file(f"data/pesteh{yesterday}_Advise_Aft.geojson")
                advice = "پس از برداشت"
            else:
                db.log_activity(user.id, "error - harvest type not found", harvest_type)
                await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=db.find_start_keyboard(user.id))
                return ConversationHandler.END
    except DriverError:
        logger.info(f"{user.id} requested harvest advice. file was not found!")
        await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات باغ شما در حال حاضر موجود نیست", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    threshold = 0.1  # degrees
    point = Point(longitude, latitude)
    idx_min_dist = harvest_data.geometry.distance(point).idxmin()
    closest_coords = harvest_data.geometry.iloc[idx_min_dist].coords[0]
    row = harvest_data.iloc[idx_min_dist]
    
    if point.distance(Point(closest_coords)) <= threshold:
        advise_3days = [row[f'Time={today}'], row[f'Time={day2}'], row[f'Time={day3}']]
        db.set_user_attribute(user.id, f"farms.{farm}.advise", {"today": advise_3days[0], "day2": advise_3days[1], "day3":advise_3days[2]})
        try:
            if pd.isna(advise_3days[0]):
                    advise = f"""
توصیه {advice} باغ شما با نام <b>#{farm.replace(" ", "_")}</b> برای #{advise_tags[0]} مورخ <b>{jdates[0]}</b>:

<pre>توصیه‌ای برای این تاریخ موجود نیست</pre>

<i>می‌توانید با استفاده از دکمه‌های زیر توصیه‌‌های مرتبط با فردا و پس‌فردا را مشاهده کنید.</i>

"""
            else:
                advise = f"""
توصیه {advice} باغ شما با نام <b>#{farm.replace(" ", "_")}</b> برای #{advise_tags[0]} مورخ <b>{jdates[0]}</b>:

<pre>{advise_3days[0]}</pre>

<i>می‌توانید با استفاده از دکمه‌های زیر توصیه‌‌های مرتبط با فردا و پس‌فردا را مشاهده کنید.</i>

"""
            await context.bot.send_message(chat_id=user.id, text=advise, reply_markup=view_advise_keyboard(farm), parse_mode=ParseMode.HTML)
            return RECV_HARVEST
        except Forbidden:
            db.set_user_attribute(user.id, "blocked", True)
            logger.info(f"user:{user.id} has blocked the bot!")
        except BadRequest:
            logger.info(f"user:{user.id} chat was not found!")
    else:
        await context.bot.send_message(chat_id=user.id, text="در حال حاضر توصیه برداشت برای باغ شما موجود نیست", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END   

harvest_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^توصیه قبل از برداشت$'), req_pre_harvest),
                      MessageHandler(filters.Regex('^توصیه بعد از برداشت$'), req_post_harvest)],
        states={
            RECV_HARVEST: [MessageHandler(filters.TEXT , recv_harvest_advice)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )