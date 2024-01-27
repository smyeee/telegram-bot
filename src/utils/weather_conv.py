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
MENU_CMDS = ['✍ sign up', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
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
            text="Chooe one of your gardens",
            reply_markup=farms_list_reply(db, user.id),
        )
        return RECV_WEATHER
    else:
        db.log_activity(user.id, "error - no farm for weather report")
        await context.bot.send_message(
            chat_id=user.id,
            text="You have not registered any garden yet",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END
    
async def req_sp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "request sp")
    user_farms = db.get_farms(user.id)
    if user_farms:
        await context.bot.send_message(
            chat_id=user.id,
            text="Choose one of your gardens",
            reply_markup=farms_list_reply(db, user.id),
        )
        return RECV_SP
    else:
        db.log_activity(user.id, "error - no farm for sp report")
        await context.bot.send_message(
            chat_id=user.id,
            text="You ha not registered any garden yet",
            reply_markup=db.find_start_keyboard(user.id),
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
        await update.message.reply_text("The operation was cancelled.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for weather report" , farm)
        await update.message.reply_text("Please try again. garden's name was wrong", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
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
Dear gardener
The weather forecast for your garden named <b>#{farm.replace(" ", "_")}</b> will be like this in the next four days 
"""
                    table([jtoday, jday2, jday3, jday4], tmin_values, tmax_values, rh_values, spd_values, rain_values)
                    with open('table.png', 'rb') as image_file:
                        await context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML)
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
                    await context.bot.send_message(chat_id=user.id, text="Unfortunately, weather information for your garden is not available at the moment", reply_markup=db.find_start_keyboard(user.id))
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
dear gardener
The weather forecast for your garden named <b>#{farm.replace(" ", "_")}</b> will be like this in the next three days 
"""
                    table([jday2, jday3, jday4], tmin_values[1:], tmax_values[1:], rh_values[1:], spd_values[1:], rain_values[1:])
                    with open('table.png', 'rb') as image_file:
                        await context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=db.find_start_keyboard(user.id), parse_mode=ParseMode.HTML)
                    # await context.bot.send_message(chat_id=user.id, text=weather_today, reply_markup=db.find_start_keyboard(user.id))
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
                    await context.bot.send_message(chat_id=user.id, text="Unfortunately, weather information for your garden is not available at the moment", reply_markup=db.find_start_keyboard(user.id))
                    return ConversationHandler.END
        except DriverError:
            logger.info(f"{user.id} requested today's weather. pesteh{today}_1.geojson was not found!")
            await context.bot.send_message(chat_id=user.id, text="Unfortunately, your garden information is not available at the moment", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        finally:
            os.system("rm table.png")
    elif user_farms[farm].get("link-status") == "To be verified":
        reply_text = "The location link sent by you has not been verified yet.\nPlease be patient until Abad admin checks."
        await context.bot.send_message(chat_id=user.id, text=reply_text,reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="The location of your garden has not been registered. Please register your location before requesting weather information.",
                                 reply_markup=db.find_start_keyboard(user.id))
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
    date_tag = 'today'

    if farm == '↩️ back':
        db.log_activity(user.id, "back")
        await update.message.reply_text("The operation was cancelled", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for sp report" , farm)
        await update.message.reply_text("Please try again. garden's name was invalid.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("The prvious operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
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
                day3 = day2
                day2 = today
                today = yesterday
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
dear gardener
The following spraying recommendation according to the weather condition of your garden named <b>#{farm.replace(" ", "_")}</b> for #{date_tag} dated <b>{jdate}</b > is sent:

<pre>There are no recommendations for this date</pre>

<i>You can see the recommendations related to tomorrow and the day after tomorrow using the buttons below.</i>
"""
                    else:
                        advise = f"""
dear gardener
The following spraying recommendation according to the weather condition of your garden named <b>#{farm.replace(" ", "_")}</b> for #{date_tag} dated <b>{jdate}</b > is sent:

<pre>{sp_3days[0]}</pre>

<i>You can see the recommendations related to tomorrow and the day after tomorrow using the buttons below.</i>
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
            await context.bot.send_message(chat_id=user.id, text="Unfortunately, your garden's information is not available at the moment", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
    elif user_farms[farm].get("link-status") == "To be verified":
        reply_text = "The location link sent by you has not been verified yet.\nPlease be patient until Abad admin checks."
        await context.bot.send_message(chat_id=user.id, text=reply_text,reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="The location of your garden has not been registered. Please register your location before requesting weather information.",
                                 reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END



async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The operation was cancelled!")
    return ConversationHandler.END   

weather_req_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('🌦 weather forecast'), req_weather_data),
                      MessageHandler(filters.Regex('🧪 spraying conditions'), req_sp_data)],
        states={
            RECV_WEATHER: [MessageHandler(filters.TEXT , recv_weather)],
            RECV_SP: [MessageHandler(filters.TEXT , recv_sp)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )