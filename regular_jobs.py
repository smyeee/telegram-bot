import database
from table_generator import table
from keyboards import start_keyboard
import pandas as pd
import geopandas as gpd
from shapely import Point
import datetime
import jdatetime
import json
from telegram.error import BadRequest, Unauthorized
from telegram import Bot
from fiona.errors import DriverError


db = database.Database()

def send_todays_data(bot: Bot, admin_list, logger):
    ids = db.user_collection.distinct("_id")
    current_day = datetime.datetime.now().strftime("%Y%m%d")
    jdate = jdatetime.datetime.now().strftime("%Y/%m/%d")
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
    jtomorrow = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    jday2 = (jdatetime.datetime.now() + jdatetime.timedelta(days=1)).strftime("%Y/%m/%d")
    jday3 = (jdatetime.datetime.now() + jdatetime.timedelta(days=2)).strftime("%Y/%m/%d")
    jday4 = (jdatetime.datetime.now() + jdatetime.timedelta(days=3)).strftime("%Y/%m/%d")
    villages = pd.read_excel("vilages.xlsx")
    weather_report_receiver_id = []
    weather_report_count = 0
    advise_today_receiver_id = []
    advise_today_count = 0
    advise_tomorrow_receiver_id = []
    advise_tomorrow_count = 0
    try:
        advise_data = gpd.read_file(f"data/pesteh{current_day}_1.geojson")
        advise_data_tomorrow = gpd.read_file(f"data/pesteh{tomorrow}_2.geojson")
        # advise_data = advise_data.dropna(subset=['Adivse'])
        for id in ids:
            farms = db.get_farms(id)
            if not farms:
                logger.info(f"user {id} has no farms yet.")
            else:
                for farm in farms:
                    longitude = farms[farm]["location"]["longitude"]
                    latitude = farms[farm]["location"]["latitude"]
                    logger.info(f"Location of farm:{farm} belonging to user:{id} --_-- lon:{longitude}, lat:{latitude}")
                    if longitude is None and farms[farm]["village"]:
                        province = farms[farm]["province"]
                        city = farms[farm]["city"]
                        village = farms[farm]["village"]
                        row = villages.loc[
                            (villages["ProvincNam"] == province)
                            & (villages["CityName"] == city)
                            & (villages["NAME"] == village)
                        ]
                        if row.empty:
                            longitude = None
                            latitude = None
                        elif not row.empty and len(row) == 1:
                            longitude = row["X"]
                            latitude = row["Y"]
                            logger.info(f"village {village} was found in villages.xlsx, lon:{longitude}, lat: {latitude}")
                    elif longitude is None:
                        logger.info(f"\nLocation of farm:{farm} belonging to user:{id} was not found\n")
                    if latitude is not None and longitude is not None:
                        logger.info(f"\nLocation of farm:{farm} belonging to user:{id} was found\n")
                        # Find the nearest point to the user's lat/long
                        point = Point(longitude, latitude)
                        threshold = 0.1  # degrees
                        idx_min_dist = advise_data.geometry.distance(point).idxmin()
                        idx_min_dist_tomorrow = advise_data_tomorrow.geometry.distance(point).idxmin()
                        closest_coords = advise_data.geometry.iloc[idx_min_dist].coords[0]
                        closest_coords_tomorrow = advise_data_tomorrow.geometry.iloc[idx_min_dist_tomorrow].coords[0]
                        if point.distance(Point(closest_coords)) <= threshold:
                            logger.info(
                                f"user's {farm} location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}"
                            )
                            row = advise_data.iloc[idx_min_dist]
                            tmin_values, tmax_values, rh_values, spd_values, rain_values = [], [], [], [], []
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
وضعیت آب و هوای باغ شما با نام <{farm}> بدین صورت خواهد بود
"""
                            weather_report = f"""
مقادیر ارسالی 
وضعیت آب و هوای باغ با نام <{farm}> بین {jdate}-{jday4} بدین صورت بود:
حداکثر دما: {tmax_values} درجه سانتیگراد
حداقل دما: {tmin_values} درجه سانتیگراد
رطوبت نسبی: {rh_values} 
سرعت باد: {spd_values} کیلومتر بر ساعت
احتمال بارش: {rain_values} درصد
"""
                            table([jdate, jday2, jday3, jday4], tmin_values, tmax_values, rh_values, spd_values, rain_values, "job-table.png")
                            advise = advise_data.iloc[idx_min_dist]["Adivse"]
                            advise_today = f"""
باغدار عزیز 
توصیه زیر با توجه به وضعیت آب و هوایی امروز باغ شما با نام <{farm}> ارسال می‌شود:

{advise}
                            """
                            try:
                                with open('job-table.png', 'rb') as image_file:
                                    bot.send_photo(chat_id=id, photo=image_file, caption=caption, reply_markup=start_keyboard())
                                username = db.user_collection.find_one({"_id": id})["username"]
                                db.log_new_message(
                                    user_id=id,
                                    username=username,
                                    message=weather_report,
                                    function="send_weather_report",
                                )
                                logger.info(f"sent todays's weather info to {id}")
                                weather_report_count += 1
                                weather_report_receiver_id.append(id)
                            except Unauthorized:
                                db.set_user_attribute(id, "blocked", True)
                                logger.info(f"user:{id} has blocked the bot!")
                                for admin in admin_list:
                                    bot.send_message(
                                        chat_id=admin, text=f"user: {id} has blocked the bot!"
                                    )
                            except BadRequest:
                                logger.info(f"user:{id} chat was not found!")
                            # logger.info(message)
                            if pd.isna(advise):
                                logger.info(
                                    f"No advice for user {id} with location (long:{longitude}, lat:{latitude}). Closest point in advise data "
                                    f"is index:{idx_min_dist} - {advise_data.iloc[idx_min_dist]['geometry']}"
                                )
                            if not pd.isna(advise):
                                try:
                                    # bot.send_message(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                                    bot.send_message(chat_id=id, text=advise_today)
                                    username = db.user_collection.find_one({"_id": id})[
                                        "username"
                                    ]
                                    db.log_new_message(
                                        user_id=id,
                                        username=username,
                                        message=advise_today,
                                        function="send_advice",
                                    )
                                    logger.info(f"sent recommendation to {id}")
                                    advise_today_count += 1
                                    advise_today_receiver_id.append(id)
                                    # bot.send_location(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                                except Unauthorized:
                                    db.set_user_attribute(id, "blocked", True)
                                    logger.info(f"user:{id} has blocked the bot!")
                                    for admin in admin_list:
                                        bot.send_message(
                                            chat_id=admin,
                                            text=f"user: {id} has blocked the bot!",
                                        )
                                except BadRequest:
                                    logger.info(f"user:{id} chat was not found!")
                        else:
                            logger.info(
                                f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))} > {threshold}"
                            )
                        if point.distance(Point(closest_coords_tomorrow)) <= threshold:
                            logger.info(
                                f"user's {farm} location: ({longitude},{latitude}) | closest point in TOMORROW's dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}"
                            )
                            advise = advise_data_tomorrow.iloc[idx_min_dist_tomorrow]["Adivse"]
                            advise_tomorrow = f"""
باغدار عزیز 
توصیه زیر با توجه به وضعیت آب و هوایی فردای باغ شما با نام <{farm}> ارسال می‌شود:

{advise}
                            """
                            
                            if pd.isna(advise):
                                logger.info(
                                    f"No advice for TOMORROW for user {id} with location (long:{longitude}, lat:{latitude}). Closest point in advise data "
                                    f"is index:{idx_min_dist} - {advise_data.iloc[idx_min_dist]['geometry']}"
                                )
                            if not pd.isna(advise):
                                try:
                                    # bot.send_message(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                                    bot.send_message(chat_id=id, text=advise_tomorrow)
                                    username = db.user_collection.find_one({"_id": id})[
                                        "username"
                                    ]
                                    db.log_new_message(
                                        user_id=id,
                                        username=username,
                                        message=advise_today,
                                        function="send_advice_tomorrow",
                                    )
                                    logger.info(f"sent recommendation to {id}")
                                    advise_tomorrow_count += 1
                                    advise_tomorrow_receiver_id.append(id)
                                    # bot.send_location(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                                except Unauthorized:
                                    db.set_user_attribute(id, "blocked", True)
                                    logger.info(f"user:{id} has blocked the bot!")
                                    for admin in admin_list:
                                        bot.send_message(
                                            chat_id=admin,
                                            text=f"user: {id} has blocked the bot!",
                                        )
                                except BadRequest:
                                    logger.info(f"user:{id} chat was not found!")
                        else:
                            logger.info(
                                f"user's location: ({longitude},{latitude}) | closest point in TOMORROW's dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))} > {threshold}"
                            )
            
        db.log_sent_messages(weather_report_receiver_id, "send_weather_report")
        logger.info(f"sent weather report to {weather_report_count} people")
        db.log_sent_messages(advise_today_receiver_id, "send_advice_to_users")
        logger.info(f"sent advice info to {advise_today_count} people")
        db.log_sent_messages(advise_tomorrow_receiver_id, "send_tomorrow_advice_to_users")
        logger.info(f"sent tomorrow's advice info to {advise_tomorrow_count} people")
        for admin in admin_list:
            bot.send_message(
                chat_id=admin, text=f"وضعیت آب و هوای {weather_report_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=weather_report_receiver_id)

            bot.send_message(
                chat_id=admin, text=f"توصیه به {advise_today_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=advise_today_receiver_id)
            bot.send_message(
                chat_id=admin, text=f"توصیه به {advise_tomorrow_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=advise_tomorrow_receiver_id)
    except DriverError:
        for admin in admin_list:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin,
                text=f"{time} file pesteh{current_day}.geojson was not found!",
            )
    except KeyError:
        for admin in admin_list:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin, text=f"key error in file pesteh{current_day}_1.geojson!"
            )

def send_up_notice(bot: Bot, admin_list, logger, message: str):
    logger.info("Sent up notice to admins...")
    for admin in admin_list:
        bot.send_message(chat_id=admin, text="بات دوباره راه‌اندازی شد"+"\n"+ message)

def get_member_count(bot: Bot, logger):
    user_data = db.user_collection.distinct("_id")
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    member_count = len(user_data)
    logger.info("Performed member count")
    db.log_member_changes(members=member_count, time=current_time)
