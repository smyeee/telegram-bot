import database
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
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    tomorrow = tomorrow.strftime("%Y%m%d")
    jtomorrow = jdatetime.datetime.now() + jdatetime.timedelta(days=1)
    jtomorrow = jtomorrow.strftime("%Y/%m/%d")
    villages = pd.read_excel("vilages.xlsx")
    weather_today_receiver_id = []
    weather_today_count = 0
    weather_tomorrow_receiver_id = []
    weather_tomorrow_count = 0
    advise_today_receiver_id = []
    advise_today_count = 0
    try:
        advise_data = gpd.read_file(f"pesteh{current_day}_1.geojson")
        with open("manual_location.json", "r") as f:
            manual_location_data = json.load(f)
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
                        logger.info("\n\n ENTERED VILLAGE.XLSX\n\n")
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
                        logger.info(f"\n\nLocation of farm:{farm} belonging to user:{id} was not found\n\n")
                    if latitude is not None and longitude is not None:
                        logger.info(f"Location of farm:{farm} belonging to user:{id} was found")
                        # Find the nearest point to the user's lat/long
                        point = Point(longitude, latitude)
                        threshold = 0.1  # degrees
                        idx_min_dist = advise_data.geometry.distance(point).idxmin()
                        closest_coords = advise_data.geometry.iloc[idx_min_dist].coords[0]
                        if point.distance(Point(closest_coords)) <= threshold:
                            logger.info(
                                f"user's {farm} location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}"
                            )
                            tmax_today = round(
                                advise_data.iloc[idx_min_dist][f"tmax_Time={current_day}"], 2
                            )
                            tmin_today = round(
                                advise_data.iloc[idx_min_dist][f"tmin_Time={current_day}"], 2
                            )
                            rh_today = round(
                                advise_data.iloc[idx_min_dist][f"rh_Time={current_day}"], 2
                            )
                            spd_today = round(
                                advise_data.iloc[idx_min_dist][f"spd_Time={current_day}"], 2
                            )
                            rain_today = round(
                                advise_data.iloc[idx_min_dist][f"rain_Time={current_day}"], 2
                            )
                            tmax_tomorrow = round(
                                advise_data.iloc[idx_min_dist][f"tmax_Time={tomorrow}"], 2
                            )
                            tmin_tomorrow = round(
                                advise_data.iloc[idx_min_dist][f"tmin_Time={tomorrow}"], 2
                            )
                            rh_tomorrow = round(advise_data.iloc[idx_min_dist][f"rh_Time={tomorrow}"], 2)
                            spd_tomorrow = round(
                                advise_data.iloc[idx_min_dist][f"spd_Time={tomorrow}"], 2
                            )
                            rain_tomorrow = round(
                                advise_data.iloc[idx_min_dist][f"rain_Time={tomorrow}"], 2
                            )
                            weather_today = f"""
        باغدار عزیز سلام
        وضعیت آب و هوای باغ شما با نام <{farm}> امروز {jdate} بدین صورت خواهد بود:
        حداکثر دما: {tmax_today} درجه سانتیگراد
        حداقل دما: {tmin_today} درجه سانتیگراد
        رطوبت نسبی: {rh_today} 
        سرعت باد: {spd_today} کیلومتر بر ساعت
        احتمال بارش: {rain_today} درصد
                            """
                            weather_tomorrow = f"""
        باغدار عزیز 
        وضعیت آب و هوای باغ شما با نام <{farm}> فردا {jtomorrow} بدین صورت خواهد بود:
        حداکثر دما: {tmax_tomorrow} درجه سانتیگراد
        حداقل دما: {tmin_tomorrow} درجه سانتیگراد
        رطوبت نسبی: {rh_tomorrow} 
        سرعت باد: {spd_tomorrow} کیلومتر بر ساعت
        احتمال بارش: {rain_tomorrow} درصد
                            """
                            
                            advise = advise_data.iloc[idx_min_dist]["Adivse"]
                            advise_today = f"""
        باغدار عزیز 
        توصیه زیر با توجه به وضعیت آب و هوایی امروز باغ شما با نام <{farm}> ارسال می‌شود:

        {advise}
                            """
                            try:
                                bot.send_message(chat_id=id, text=weather_today)
                                username = db.user_collection.find_one({"_id": id})["username"]
                                db.log_new_message(
                                    user_id=id,
                                    username=username,
                                    message=weather_today,
                                    function="send_weather_today",
                                )
                                logger.info(f"sent todays's weather info to {id}")
                                weather_today_count += 1
                                weather_today_receiver_id.append(id)

                                bot.send_message(chat_id=id, text=weather_tomorrow)
                                db.log_new_message(
                                    user_id=id,
                                    username=username,
                                    message=weather_tomorrow,
                                    function="send_weather",
                                )
                                logger.info(f"sent tomorrow's weather info to {id}")
                                weather_tomorrow_count += 1
                                weather_tomorrow_receiver_id.append(id)
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
            
        db.log_sent_messages(weather_today_receiver_id, "send_todays_weather")
        logger.info(f"sent todays's weather info to {weather_today_count} people")
        db.log_sent_messages(weather_tomorrow_receiver_id, "send_todays_weather")
        logger.info(f"sent tomorrow's weather info to {weather_tomorrow_count} people")
        db.log_sent_messages(advise_today_receiver_id, "send_advice_to_users")
        logger.info(f"sent advice info to {advise_today_count} people")
        for admin in admin_list:
            bot.send_message(
                chat_id=admin, text=f"وضعیت آب و هوای امروز {weather_today_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=weather_today_receiver_id)

            bot.send_message(
                chat_id=admin, text=f"وضعیت آب و هوای فردای {weather_tomorrow_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=weather_tomorrow_receiver_id)

            bot.send_message(
                chat_id=admin, text=f"توصیه به {advise_today_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=advise_today_receiver_id)
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

def send_todays_weather(bot: Bot, admin_list, logger):
    ids = db.user_collection.distinct("_id")
    current_day = datetime.datetime.now().strftime("%Y%m%d")
    jdate = jdatetime.datetime.now().strftime("%Y/%m/%d")
    villages = pd.read_excel("vilages.xlsx")
    message_count = 0
    receiver_id = []
    try:
        advise_data = gpd.read_file(f"pesteh{current_day}_1.geojson")
        with open("manual_location.json", "r") as f:
            manual_location_data = json.load(f)
        # advise_data = advise_data.dropna(subset=['Adivse'])
        for id in ids:
            user_document = db.user_collection.find_one({"_id": id})
            try:
                user_document["locations"][0].get("longitude")
            except IndexError:
                db.set_user_attribute(id, "locations", {}, array=True)
                logger.info(f"added an empty dict to {id} locations array")
            # if user_data[id].get("province") == prov:
            if str(id) in manual_location_data:
                longitude = manual_location_data[str(id)]["longitude"]
                latitude = manual_location_data[str(id)]["latitude"]
            elif user_document["locations"][0].get("longitude"):
                logger.info(f"LOCATION: {user_document.get('locations')}")
                longitude = user_document["locations"][0]["longitude"]
                latitude = user_document["locations"][0]["latitude"]
            elif (
                not user_document["locations"][0].get("longitude")
                and user_document["villages"][0] != ""
            ):
                province = user_document["provinces"][0]
                city = user_document["cities"][0]
                village = user_document["villages"][0]
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
                    logger.info(f"village {village} was found in villages.xlsx")
            else:
                logger.info(f"Location of user:{id} was not found")
                latitude = None
                longitude = None

            if latitude is not None and longitude is not None:
                logger.info(f"Location of user:{id} was found")
                # Find the nearest point to the user's lat/long
                point = Point(longitude, latitude)
                threshold = 0.1  # degrees
                idx_min_dist = advise_data.geometry.distance(point).idxmin()
                closest_coords = advise_data.geometry.iloc[idx_min_dist].coords[0]
                if point.distance(Point(closest_coords)) <= threshold:
                    logger.info(
                        f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}"
                    )
                    tmax = round(
                        advise_data.iloc[idx_min_dist][f"tmax_Time={current_day}"], 2
                    )
                    tmin = round(
                        advise_data.iloc[idx_min_dist][f"tmin_Time={current_day}"], 2
                    )
                    rh = round(
                        advise_data.iloc[idx_min_dist][f"rh_Time={current_day}"], 2
                    )
                    spd = round(
                        advise_data.iloc[idx_min_dist][f"spd_Time={current_day}"], 2
                    )
                    rain = round(
                        advise_data.iloc[idx_min_dist][f"rain_Time={current_day}"], 2
                    )
                    message = f"""
باغدار عزیز سلام
وضعیت آب و هوای باغ شما امروز {jdate} بدین صورت خواهد بود:
حداکثر دما: {tmax} درجه سانتیگراد
حداقل دما: {tmin} درجه سانتیگراد
رطوبت نسبی: {rh} 
سرعت باد: {spd} کیلومتر بر ساعت
احتمال بارش: {rain} درصد
                    """
                    # logger.info(message)
                    # if pd.isna(advise):
                    #     logger.info(f"No advice for user {id} with location (long:{longitude}, lat:{latitude}). Closest point in advise data "
                    #                 f"is index:{idx_min_dist} - {advise_data.iloc[idx_min_dist]['geometry']}")
                    # if not pd.isna(advise):
                    try:
                        # bot.send_message(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                        bot.send_message(chat_id=id, text=message)
                        username = db.user_collection.find_one({"_id": id})["username"]
                        db.log_new_message(
                            user_id=id,
                            username=username,
                            message=message,
                            function="send_weather",
                        )
                        logger.info(f"sent todays's weather info to {id}")
                        message_count += 1
                        receiver_id.append(id)
                        # bot.send_location(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                    except Unauthorized:
                        db.set_user_attribute(id, "blocked", True)
                        logger.info(f"user:{id} has blocked the bot!")
                        for admin in admin_list:
                            bot.send_message(
                                chat_id=admin, text=f"user: {id} has blocked the bot!"
                            )
                    except BadRequest:
                        logger.info(f"user:{id} chat was not found!")
                else:
                    logger.info(
                        f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}"
                    )
        db.log_sent_messages(receiver_id, "send_todays_weather")
        logger.info(f"sent todays's weather info to {message_count} people")
        for admin in admin_list:
            bot.send_message(
                chat_id=admin, text=f"وضعیت آب و هوای {message_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=receiver_id)
    except DriverError:
        for admin in admin_list:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin,
                text=f"{time} file pesteh{current_day}_1.geojson was not found!",
            )
    except KeyError:
        for admin in admin_list:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin, text=f"key error in file pesteh{current_day}_1.geojson!"
            )

def send_tomorrows_weather(bot: Bot, admin_list, logger):
    ids = db.user_collection.distinct("_id")
    current_day = datetime.datetime.now().strftime("%Y%m%d")
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    tomorrow = tomorrow.strftime("%Y%m%d")
    jtomorrow = jdatetime.datetime.now() + jdatetime.timedelta(days=1)
    jtomorrow = jtomorrow.strftime("%Y/%m/%d")
    villages = pd.read_excel("vilages.xlsx")
    message_count = 0
    receiver_id = []
    try:
        advise_data = gpd.read_file(f"pesteh{current_day}_1.geojson")
        with open("manual_location.json", "r") as f:
            manual_location_data = json.load(f)
        # advise_data = advise_data.dropna(subset=['Adivse'])
        for id in ids:
            user_document = db.user_collection.find_one({"_id": id})
            # if user_data[id].get("province") == prov:
            if str(id) in manual_location_data:
                longitude = manual_location_data[str(id)]["longitude"]
                latitude = manual_location_data[str(id)]["latitude"]
            elif user_document["locations"][0].get("longitude"):
                logger.info(f"LOCATION: {user_document.get('locations')}")
                longitude = user_document["locations"][0]["longitude"]
                latitude = user_document["locations"][0]["latitude"]
            elif (
                not user_document["locations"][0].get("longitude")
                and user_document["villages"][0] != ""
            ):
                province = user_document["provinces"][0]
                city = user_document["cities"][0]
                village = user_document["villages"][0]
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
                    logger.info(f"village {village} was found in villages.xlsx")
            else:
                logger.info(f"Location of user:{id} was not found")
                latitude = None
                longitude = None

            if latitude is not None and longitude is not None:
                logger.info(f"Location of user:{id} was found")
                # Find the nearest point to the user's lat/long
                point = Point(longitude, latitude)
                threshold = 0.1  # degrees
                idx_min_dist = advise_data.geometry.distance(point).idxmin()
                closest_coords = advise_data.geometry.iloc[idx_min_dist].coords[0]
                if point.distance(Point(closest_coords)) <= threshold:
                    logger.info(
                        f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}"
                    )
                    tmax = round(
                        advise_data.iloc[idx_min_dist][f"tmax_Time={tomorrow}"], 2
                    )
                    tmin = round(
                        advise_data.iloc[idx_min_dist][f"tmin_Time={tomorrow}"], 2
                    )
                    rh = round(advise_data.iloc[idx_min_dist][f"rh_Time={tomorrow}"], 2)
                    spd = round(
                        advise_data.iloc[idx_min_dist][f"spd_Time={tomorrow}"], 2
                    )
                    rain = round(
                        advise_data.iloc[idx_min_dist][f"rain_Time={tomorrow}"], 2
                    )
                    message = f"""
باغدار عزیز 
وضعیت آب و هوای باغ شما فردا {jtomorrow} بدین صورت خواهد بود:
حداکثر دما: {tmax} درجه سانتیگراد
حداقل دما: {tmin} درجه سانتیگراد
رطوبت نسبی: {rh} 
سرعت باد: {spd} کیلومتر بر ساعت
احتمال بارش: {rain} درصد
                    """
                    # logger.info(message)
                    # if pd.isna(advise):
                    #     logger.info(f"No advice for user {id} with location (long:{longitude}, lat:{latitude}). Closest point in advise data "
                    #                 f"is index:{idx_min_dist} - {advise_data.iloc[idx_min_dist]['geometry']}")
                    # if not pd.isna(advise):
                    try:
                        # bot.send_message(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                        bot.send_message(chat_id=id, text=message)
                        username = db.user_collection.find_one({"_id": id})["username"]
                        db.log_new_message(
                            user_id=id,
                            username=username,
                            message=message,
                            function="send_weather",
                        )
                        logger.info(f"sent tomorrow's weather info to {id}")
                        message_count += 1
                        receiver_id.append(id)
                        # bot.send_location(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                    except Unauthorized:
                        db.set_user_attribute(id, "blocked", True)
                        logger.info(f"user:{id} has blocked the bot!")
                        for admin in admin_list:
                            bot.send_message(
                                chat_id=admin, text=f"user: {id} has blocked the bot!"
                            )
                    except BadRequest:
                        logger.info(f"user:{id} chat was not found!")
                else:
                    logger.info(
                        f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}"
                    )
        db.log_sent_messages(receiver_id, "send_todays_weather")
        logger.info(f"sent tomorrow's weather info to {message_count} people")
        for admin in admin_list:
            bot.send_message(
                chat_id=admin, text=f"وضعیت آب و هوای {message_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=receiver_id)
    except DriverError:
        for admin in admin_list:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin,
                text=f"{time} file pesteh{current_day}_1.geojson was not found!",
            )
    except KeyError:
        for admin in admin_list:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin, text=f"key error in file pesteh{current_day}_1.geojson!"
            )

def send_up_notice(bot: Bot, admin_list, logger):
    logger.info("Sent up notice to admins...")
    for admin in admin_list:
        bot.send_message(chat_id=admin, text="بات دوباره راه‌اندازی شد")

def get_member_count(bot: Bot, logger):
    user_data = db.user_collection.distinct("_id")
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    member_count = len(user_data)
    logger.info("Performed member count")
    db.log_member_changes(members=member_count, time=current_time)
