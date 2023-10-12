import logging
from logging.handlers import RotatingFileHandler
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
from .keyboards import (
    start_keyboard,
    farms_list_reply,
    view_sp_advise_keyboard
)
from .table_generator import table
from telegram.constants import ParseMode

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

RECV_WEATHER, RECV_SP = range(2)
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده باغ ها', '➕ اضافه کردن باغ', '🗑 حذف باغ ها', '✏️ ویرایش باغ ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()

# START OF REQUEST WEATHER CONVERSATION
async def req_weather_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "request weather")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return RECV_WEATHER
    else:
        db.log_activity(user.id, "error - no farm for weather report")
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=start_keyboard(),
        )
        return ConversationHandler.END
    
async def req_sp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "request sp")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return RECV_SP
    else:
        db.log_activity(user.id, "error - no farm for sp report")
        await context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=start_keyboard(),
        )
        return ConversationHandler.END

async def recv_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    today = datetime.datetime.now().strftime("%Y%m%d")
    day2 = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
    day3 = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y%m%d")
    day4 = (datetime.datetime.now() + datetime.timedelta(days=3)).strftime("%Y%m%d")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    jtoday = jdatetime.datetime.now().strftime("%Y/%m/%d")
    jday2 = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    jday3 = (jdatetime.datetime.now() + jdatetime.timedelta(days=2)).strftime("%Y/%m/%d")
    jday4 = (jdatetime.datetime.now() + jdatetime.timedelta(days=3)).strftime("%Y/%m/%d")
    if farm == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await update.message.reply_text("عملیات لغو شد", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for weather report" , farm)
        await update.message.reply_text("لطفا دوباره تلاش کنید. نام باغ اشتباه بود", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm for weather report", farm)
    longitude = user_farms[farm]["location"]["longitude"]
    latitude = user_farms[farm]["location"]["latitude"]
    
    if longitude is not None:
        try:
            if datetime.time(7, 0).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(20, 30).strftime("%H%M"):    
                weather_data = gpd.read_file(f"data/Iran{today}_weather.geojson")
                point = Point(longitude, latitude)
                threshold = 0.1  # degrees
                idx_min_dist = weather_data.geometry.distance(point).idxmin()
                closest_coords = weather_data.geometry.iloc[idx_min_dist].coords[0]
                if point.distance(Point(closest_coords)) <= threshold:
                    row = weather_data.iloc[idx_min_dist]
                    tmin_values , tmax_values , rh_values , spd_values , rain_values = [], [], [], [], []
                    for key, value in row.items():
                        if "tmin_Time=" in key:
                            tmin_values.append(round(value, 1))
                        elif "tmax_Time=" in key:
                            tmax_values.append(round(value, 1))
                        elif "rh_Time=" in key:
                            rh_values.append(round(value, 1))
                        elif "spd_Time=" in key:
                            spd_values.append(round(value, 1))
                        elif "rain_Time=" in key:
                            rain_values.append(round(value, 1))
                    caption = f"""
باغدار عزیز 
پیش‌بینی وضعیت آب و هوای باغ شما با نام <b>#{farm.replace(" ", "_")}</b> در چهار روز آینده بدین صورت خواهد بود
"""
                    table([jtoday, jday2, jday3, jday4], tmin_values, tmax_values, rh_values, spd_values, rain_values)
                    with open('table.png', 'rb') as image_file:
                        await context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=start_keyboard(), parse_mode=ParseMode.HTML)
                    username = user.username
                    db.log_new_message(
                        user_id=user.id,
                        username=username,
                        message=caption,
                        function="req_weather_4",
                        )
                    db.log_activity(user.id, "received 4-day weather reports")
                    return ConversationHandler.END
                else:
                    await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات هواشناسی باغ شما در حال حاضر موجود نیست", reply_markup=start_keyboard())
                    return ConversationHandler.END
            else:
                weather_data = gpd.read_file(f"data/Iran{yesterday}_weather.geojson")
                point = Point(longitude, latitude)
                threshold = 0.1  # degrees
                idx_min_dist = weather_data.geometry.distance(point).idxmin()
                closest_coords = weather_data.geometry.iloc[idx_min_dist].coords[0]
                if point.distance(Point(closest_coords)) <= threshold:
                    row = weather_data.iloc[idx_min_dist]
                    tmin_values , tmax_values , rh_values , spd_values , rain_values = [], [], [], [], []
                    for key, value in row.items():
                        if "tmin_Time=" in key:
                            tmin_values.append(round(value, 1))
                        elif "tmax_Time=" in key:
                            tmax_values.append(round(value, 1))
                        elif "rh_Time=" in key:
                            rh_values.append(round(value, 1))
                        elif "spd_Time=" in key:
                            spd_values.append(round(value, 1))
                        elif "rain_Time=" in key:
                            rain_values.append(round(value, 1))
                    caption = f"""
باغدار عزیز 
پیش‌بینی وضعیت آب و هوای باغ شما با نام <b>#{farm.replace(" ", "_")}</b> در سه روز آینده بدین صورت خواهد بود
"""
                    table([jday2, jday3, jday4], tmin_values[1:], tmax_values[1:], rh_values[1:], spd_values[1:], rain_values[1:])
                    with open('table.png', 'rb') as image_file:
                        await context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=start_keyboard(), parse_mode=ParseMode.HTML)
                    # await context.bot.send_message(chat_id=user.id, text=weather_today, reply_markup=start_keyboard())
                    username = user.username
                    db.log_new_message(
                        user_id=user.id,
                        username=username,
                        message=caption,
                        function="req_weather_3",
                        )
                    db.log_activity(user.id, "received 3-day weather reports")
                    return ConversationHandler.END
                else:
                    await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات هواشناسی باغ شما در حال حاضر موجود نیست", reply_markup=start_keyboard())
                    return ConversationHandler.END
        except DriverError:
            logger.info(f"{user.id} requested today's weather. pesteh{today}_1.geojson was not found!")
            await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات باغ شما در حال حاضر موجود نیست", reply_markup=start_keyboard())
            return ConversationHandler.END
        finally:
            os.system("rm table.png")
    else:
        await context.bot.send_message(chat_id=user.id, text="موقعیت باغ شما ثبت نشده است. لظفا پیش از درخواست اطلاعات هواشناسی نسبت به ثبت موققعیت اقدام فرمایید.",
                                 reply_markup=start_keyboard())
        return ConversationHandler.END

async def recv_sp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    farm = update.message.text
    user_farms = db.get_farms(user.id)
    today = datetime.datetime.now().strftime("%Y%m%d")
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    day2 = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
    day3 = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y%m%d")
    jdate = jdatetime.datetime.now().strftime("%Y/%m/%d")
    date_tag = 'امروز'

    if farm == '↩️ بازگشت':
        db.log_activity(user.id, "back")
        await update.message.reply_text("عملیات لغو شد", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for sp report" , farm)
        await update.message.reply_text("لطفا دوباره تلاش کنید. نام باغ اشتباه بود", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm for sp report", farm)
    longitude = user_farms[farm]["location"]["longitude"]
    latitude = user_farms[farm]["location"]["latitude"]
    if longitude is not None:
        try:
            if datetime.time(7, 0).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(20, 30).strftime("%H%M"):    
                sp_data = gpd.read_file(f"data/Iran{today}_AdviseSP.geojson")
            else:
                sp_data = gpd.read_file(f"data/Iran{yesterday}_AdviseSP.geojson")
            # sp_data = gpd.read_file(f"data/pesteh{today}_AdviseSP.geojson")
            point = Point(longitude, latitude)
            threshold = 0.1  # degrees
            idx_min_dist = sp_data.geometry.distance(point).idxmin()
            closest_coords = sp_data.geometry.iloc[idx_min_dist].coords[0]
            if point.distance(Point(closest_coords)) <= threshold:
                row = sp_data.iloc[idx_min_dist]
                sp_3days = [row[f'Time={today}'], row[f'Time={day2}'], row[f'Time={day3}']]
                        # advise_3days_no_nan = ["" for text in advise_3days if pd.isna(text)]
                        # logger.info(f"{advise_3days}\n\n{advise_3days_no_nan}\n----------------------------")
                db.set_user_attribute(user.id, f"farms.{farm}.sp-advise", {"today": sp_3days[0], "day2": sp_3days[1], "day3":sp_3days[2]})
                try:
                    if pd.isna(sp_3days[0]):
                        advise = f"""
باغدار عزیز 
توصیه محلول‌‌پاشی زیر با توجه به وضعیت آب و هوایی باغ شما با نام <b>#{farm.replace(" ", "_")}</b> برای #{date_tag} مورخ <b>{jdate}</b> ارسال می‌شود:

<pre>توصیه‌ای برای این تاریخ موجود نیست</pre>

<i>می‌توانید با استفاده از دکمه‌های زیر توصیه‌‌های مرتبط با فردا و پس‌فردا را مشاهده کنید.</i>
"""
                    else:
                        advise = f"""
باغدار عزیز 
توصیه محلول‌‌پاشی زیر با توجه به وضعیت آب و هوایی باغ شما با نام <b>#{farm.replace(" ", "_")}</b> برای #{date_tag} مورخ <b>{jdate}</b> ارسال می‌شود:

<pre>{sp_3days[0]}</pre>

<i>می‌توانید با استفاده از دکمه‌های زیر توصیه‌‌های مرتبط با فردا و پس‌فردا را مشاهده کنید.</i>
"""
                    await context.bot.send_message(chat_id=user.id, text=advise, reply_markup=view_sp_advise_keyboard(farm), parse_mode=ParseMode.HTML)
                    username = user.username
                    db.log_new_message(
                        user_id=user.id,
                        username=username,
                        message=advise,
                        function="send_advice",
                        )
                    db.log_activity(user.id, "received sp advice")
                except Forbidden:
                    db.set_user_attribute(user.id, "blocked", True)
                    logger.info(f"user:{user.id} has blocked the bot!")
                except BadRequest:
                    logger.info(f"user:{user.id} chat was not found!")
                finally:
                    return ConversationHandler.END
        except DriverError:
            logger.info(f"{user.id} requested today's weather. pesteh{today}_AdviseSP.geojson was not found!")
            await context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات باغ شما در حال حاضر موجود نیست", reply_markup=start_keyboard())
            return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="موقعیت باغ شما ثبت نشده است. لظفا پیش از درخواست اطلاعات هواشناسی نسبت به ثبت موققعیت اقدام فرمایید.",
                                 reply_markup=start_keyboard())
        return ConversationHandler.END



async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END   

weather_req_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('🌦 پیش‌بینی هواشناسی'), req_weather_data),
                      MessageHandler(filters.Regex('🧪 شرایط محلول‌پاشی'), req_sp_data)],
        states={
            RECV_WEATHER: [MessageHandler(filters.TEXT , recv_weather)],
            RECV_SP: [MessageHandler(filters.TEXT , recv_sp)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )