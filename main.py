import json
import logging
from logging.handlers import RotatingFileHandler
import datetime
import jdatetime
import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
from telegram import (
    Bot,
    Location,
    KeyboardButton,
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CallbackContext,
    ConversationHandler,
    PicklePersistence,
    Dispatcher,
)
from telegram import ParseMode
from telegram.error import BadRequest, Unauthorized, NetworkError
import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fiona.errors import DriverError
import warnings
import database
from regular_jobs import send_todays_data, send_up_notice, get_member_count
from keyboards import (
    start_keyboard,
    stats_keyboard,
    get_product_keyboard,
    get_province_keyboard,
    farms_list_reply,
    edit_keyboard_reply,
    conf_del_keyboard,
    back_button,
    choose_role
)
from table_generator import table


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

# Constants for ConversationHandler states
CHOOSE_RECEIVERS, BROADCAST = range(2)
HANDLE_QUERY = 0
(
    ASK_PRODUCT,
    ASK_PROVINCE,
    ASK_CITY,
    ASK_VILLAGE,
    ASK_AREA,
    ASK_LOCATION,
    HANDLE_LOCATION,
    HANDLE_LINK
) = range(8)
(
    EDIT_PROVINCE,
    EDIT_CITY,
    EDIT_VILLAGE,
    EDIT_AREA,
    EDIT_LOCATION,
    HANDLE_LOCATION_EDIT,
) = range(6)
ASK_FARM_NAME, ASK_LONGITUDE, ASK_LATITUDE, HANDLE_LAT_LONG = range(4)
ASK_PHONE, HANDLE_PHONE = range(2)
VIEW_FARM = range(1)
RECV_WEATHER = range(1)
CHOOSE_ATTR, EDIT_FARM, HANDLE_EDIT, HANDLE_EDIT_LINK = range(4)
CONFIRM_DELETE, DELETE_FARM = range(2)
TOKEN = os.environ["AGRIWEATHBOT_TOKEN"]

db = database.Database()
# db.populate_mongodb_from_pickle()
REQUIRED_KEYS = [
    "products",
    "provinces",
    "cities",
    "villages",
    "areas",
    "locations",
    "name",
    "phone-number",
]
PROVINCES = ["کرمان", "خراسان رضوی", "خراسان جنوبی", "یزد", "فارس", "سمنان", "سایر"]
PRODUCTS = [
    "پسته اکبری",
    "پسته اوحدی",
    "پسته احمدآقایی",
    "پسته بادامی",
    "پسته فندقی",
    "پسته کله قوچی",
    "پسته ممتاز",
    "سایر",
]
ADMIN_LIST = [103465015, 31583686, 391763080]#, 216033407]


def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    # Check if the user has already signed up
    if not db.check_if_user_exists(user_id=user.id):
        user_data["username"] = user.username
        user_data["blocked"] = False
        db.add_new_user(user_id=user.id, username=user.username)
        logger.info(f"{user.username} (id: {user.id}) started the bot.")
        reply_text = """
باغدار عزیز سلام
از این که به ما اعتماد کردید متشکریم.
برای دریافت توصیه‌های کاربردی هواشناسی از قبیل سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، نیاز سرمایی و … ابتدا ثبت نام خود را کامل کرده
و سپس باغ های خود را ثبت کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
تلفن ثابت: 02164063399
                """
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ASK_PROVINCE
    else:
        reply_text = """
باغدار عزیز سلام
از این که به ما اعتماد کردید متشکریم.
برای دریافت توصیه‌های کاربردی هواشناسی از قبیل سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، نیاز سرمایی و … باغ های خد را در بات ثبت کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
تلفن ثابت: 02164063399
                """
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END

def send(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in ADMIN_LIST:
        update.message.reply_text(
            "گیرنده پیام کیست؟",
            reply_markup=choose_role()
        )
        return CHOOSE_RECEIVERS
    else:
        return ConversationHandler.END

def choose_receivers(update: Update, context: CallbackContext):
    # user_data = db.user_collection.find()
    user_data = context.user_data
    message_text = update.message.text
    if not message_text:
        update.message.reply_text(
            "گیرنده پیام کیست؟",
            reply_markup=choose_role()
        )
        return CHOOSE_RECEIVERS
    elif message_text == "/cancel":
        update.message.reply_text("عملیات کنسل شد!", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text == "بازگشت":
        update.message.reply_text("عملیات کنسل شد!", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text == "تمام کاربران":
        user_data["receiver_list"] = db.user_collection.distinct("_id")
        user_data["receiver_type"] = "to All Users"
        update.message.reply_text("لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:", 
                                  reply_markup=back_button())
        return BROADCAST
    elif message_text == "بدون لوکیشن":
        users = db.get_users_without_location()
        user_data["receiver_list"] = users
        user_data["receiver_type"] = "to Users W/O Location"
        update.message.reply_text("لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:", 
                                  reply_markup=back_button())
        return BROADCAST
    elif message_text == "بدون شماره تلفن":
        users = db.get_users_without_phone()
        user_data["receiver_list"] = users
        user_data["receiver_type"] = "to Users W/O Phone Number"
        update.message.reply_text("لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:", 
                                  reply_markup=back_button())
        return BROADCAST
    else:
        update.message.reply_text("عملیات کنسل شد!", reply_markup=start_keyboard())
        return ConversationHandler.END

def broadcast(update: Update, context: CallbackContext):
    user_data = context.user_data
    message_text = update.message.text
    message_poll = update.message.poll
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    receiver_list = user_data['receiver_list']
    i = 0
    receivers = []
    if message_text == "/cancel":
        update.message.reply_text("عملیات کنسل شد!", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif message_text == "بازگشت":
        update.message.reply_text(
            "گیرنده پیام کیست؟",
            reply_markup=choose_role()
        )
        return CHOOSE_RECEIVERS
    else:
        for user_id in receiver_list:
            try:
                if message_poll:
                    context.bot.forward_message(chat_id=user_id, from_chat_id=chat_id, message_id=message_id)
                else:
                    context.bot.copy_message(chat_id=user_id, from_chat_id=chat_id, message_id=message_id)
                # context.bot.send_message(user_id, message)
                username = db.user_collection.find_one({"_id": user_id})["username"]
                db.log_new_message(
                    user_id=user_id,
                    username=username,
                    message=message_text,
                    function=f"broadcast {user_data['receiver_type']}"
                )
                receivers.append(user_id)
                i += 1
            except Unauthorized:
                logger.error(f"user {user_id} blocked the bot")
                db.set_user_attribute(user_id, "blocked", True)
            except BadRequest:
                logger.error(f"chat with {user_id} not found.")
    db.log_sent_messages(receivers, f"broadcast {user_data['receiver_type']}")
    for id in ADMIN_LIST:
        context.bot.send_message(id, f"پیام برای {i} نفر از {len(receiver_list)} نفر ارسال شد."
                                 , reply_markup=start_keyboard())
    return ConversationHandler.END

def set_loc(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in ADMIN_LIST:
        update.message.reply_text(
            "لطفا شناسه کاربر مورد نظر را بنویسید یا برای لغو /cancel را بزنید:",
        )
        return ASK_FARM_NAME
    else:
        return ConversationHandler.END

def ask_farm_name(update: Update, context: CallbackContext):
    user_data = context.user_data
    target_id = update.message.text
    if target_id == "/cancel":
        update.message.reply_text("عملیات کنسل شد!")
        return ConversationHandler.END
    elif not target_id:
        update.message.reply_text(
             "لطفا شناسه کاربر مورد نظر را بنویسید یا برای لغو /cancel را بزنید:",
        )
        return ASK_FARM_NAME
    elif not db.check_if_user_exists(int(target_id)):
        update.message.reply_text("چنین کاربری در دیتابیس وجود نداشت. دوباره تلاش کنید. \n/cancel")
        return ASK_FARM_NAME
    user_data["target"] = target_id
    update.message.reply_text(f"نام باغ چیست؟")
    return ASK_LONGITUDE

def ask_longitude(update: Update, context: CallbackContext):
    user_data = context.user_data
    farm_name = update.message.text
    farm_names = list(db.get_farms(int(user_data['target'])))
    if farm_name == "/cancel":
        update.message.reply_text("عملیات کنسل شد!")
        return ConversationHandler.END
    elif not farm_name:
        update.message.reply_text(f"نام باغ چیست؟ \n/cancel")
        return ASK_LONGITUDE
    elif farm_name not in farm_names:
        update.message.reply_text(f"نام باغ اشتباه است. دوباره تلاش کنید. \n/cancel")
        return ASK_LONGITUDE
    user_data["farm_name"] = farm_name
    update.message.reply_text(f"what's the longitude of {user_data['target']}? \ndo you want to /cancel ?")
    return ASK_LATITUDE

def ask_latitude(update: Update, context: CallbackContext):
    user_data = context.user_data
    longitude = update.message.text
    if longitude == "/cancel":
        update.message.reply_text("عملیات کنسل شد!")
        return ConversationHandler.END
    if not longitude:
        update.message.reply_text(f"what's the longitude of {longitude}? \ndo you want to /cancel ?")
        return ASK_LATITUDE
    user_data["long"] = longitude
    update.message.reply_text(f"what's the latitude of {user_data['target']}?\ndo you want to /cancel ?")
    return HANDLE_LAT_LONG

def handle_lat_long(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    latitude = update.message.text
    if latitude == "/cancel":
        update.message.reply_text("عملیات کنسل شد!")
        return ConversationHandler.END
    if not latitude:
        update.message.reply_text(f"what's the latitude of {latitude}? \ndo you want to /cancel ?")
        return HANDLE_LAT_LONG
    user_data["lat"] = latitude
    db.set_user_attribute(int(user_data["target"]), f"farms.{user_data['farm_name']}.location.longitude", float(user_data["long"]))
    db.set_user_attribute(int(user_data["target"]), f"farms.{user_data['farm_name']}.location.latitude", float(user_data["lat"]))
    context.bot.send_location(chat_id=user.id, latitude=float(user_data["lat"]), longitude=float(user_data["long"]))
    context.bot.send_message(chat_id=int(user_data["target"]), text=f"لوکیشن باغ شما با نام {user_data['farm_name']} ثبت شد.")
    context.bot.send_location(chat_id=int(user_data["target"]), latitude=float(user_data["lat"]), longitude=float(user_data["long"]))
    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END


def bot_stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in ADMIN_LIST:
        update.message.reply_text(
            "آمار مورد نظر را انتخاب کنید", reply_markup=stats_keyboard()
        )


def button(update: Update, context: CallbackContext):
    stat = update.callback_query
    id = update.effective_user.id
    if stat.data == "member_count":
        member_count = db.bot_collection.find_one()["num-members"][-1]
        context.bot.send_message(chat_id=id, text=f"تعداد کل اعضا: {member_count}")
    elif stat.data == "member_count_change":
        members_doc = db.bot_collection.find_one()
        if len(members_doc["time-stamp"]) < 15:
            plt.plot(members_doc["time-stamp"], members_doc["num-members"], "r-")
        else:
            plt.plot(
                members_doc["time-stamp"][-15:], members_doc["num-members"][-15:], "r-"
            )
        plt.xlabel("Time")
        plt.ylabel("Members")
        plt.title("Bot Members Over Time")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig("member-change.png")
        photo = open("member-change.png", "rb")
        context.bot.send_photo(chat_id=id, photo=photo)
        photo.close()
        os.remove("member-change.png")
    elif stat.data == "excel_download":
        try:
            output_file = "member-data.xlsx"
            db.to_excel(output_file=output_file)
            doc = open(output_file, "rb")
            context.bot.send_document(chat_id=id, document=doc)
            doc.close()
            os.remove(output_file)
        except:
            logger.info("encountered error during excel download!")

def view_farm_keyboard(update: Update, context: CallbackContext):
    user = update.effective_user
    db.log_activity(user.id, "chose view farms")
    user_farms = db.get_farms(user.id)
    if user_farms:
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return VIEW_FARM
    else:
        context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=start_keyboard(),
        )
        return ConversationHandler.END

def view_farm(update: Update, context: CallbackContext):
    farm = update.message.text
    # farm = f"view{farm}"
    user = update.effective_user
    user_farms = db.get_farms(user.id)
    user_farms_names = list(db.get_farms(user.id).keys())
    if farm not in user_farms_names and farm != "↩️ بازگشت":
        db.log_activity(user.id, "error - chose wrong farm to view")
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return VIEW_FARM
    if farm == "↩️ بازگشت":
        db.log_activity(user.id, "back")
        context.bot.send_message(
            chat_id=user.id, text="عملیات کنسل شد!", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    if not user_farms[farm].get("location") == {}:
        latitude = user_farms[farm].get("location").get("latitude")
        longitude = user_farms[farm].get("location").get("longitude")
    else:
        latitude = None
        longitude = None
    message_id = update.effective_message.message_id
    try:
        text = f"""
<b>{farm}</b>
محصول باغ: {user_farms[farm].get("product")}
مساحت: {user_farms[farm].get("area")}
آدرس انتخاب شده ⬇️
"""
        context.bot.send_message(chat_id=user.id, text=text, parse_mode=ParseMode.HTML)
        if latitude and longitude:
            context.bot.send_location(
                chat_id=user.id,
                latitude=latitude,
                longitude=longitude,
                reply_markup=farms_list_reply(db, user.id),
            )
        else:
            context.bot.send_message(
                chat_id=user.id,
                text=f"متاسفانه موقعیت <{farm}> ثبت نشده است. "
                "می توانید از طریق گزینه ویرایش باغ موقعیت آن را ثبت کنید.",
                reply_markup=farms_list_reply(db, user.id),
            )
        db.log_activity(user.id, "viewed a farm")
    except KeyError:
        logger.info(f"key {farm} doesn't exist.")
        return ConversationHandler.END

def edit_farm_keyboard(update: Update, context: CallbackContext):
    user = update.effective_user
    db.log_activity(user.id, "start edit")
    user_farms = db.get_farms(user.id)
    if user_farms:
        # context.bot.send_message(chat_id=user.id, text="یکی از باغ های خود را ویرایش کنید", reply_markup=farms_list(db, user.id, view=False, edit=True))
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را ویرایش کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    else:
        context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=start_keyboard(),
        )
        return ConversationHandler.END

def choose_attr_to_edit(update: Update, context: CallbackContext):
    # farm = update.callback_query.data
    farm = update.message.text

    user = update.effective_user
    user_data = context.user_data
    user_data["selected_farm"] = farm
    user_farms = list(db.get_farms(user.id).keys())
    if farm not in user_farms and farm != "↩️ بازگشت":
        db.log_activity(user.id, "error - chose wrong farm")
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را ویرایش کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    if farm == "↩️ بازگشت":
        db.log_activity(user.id, "back")
        context.bot.send_message(
            chat_id=user.id, text="عملیات کنسل شد!", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm to edit")
    message_id = update.effective_message.message_id
    try:
        # context.bot.edit_message_text(chat_id=user.id, message_id=message_id, text=f"انتخاب مولفه برای ویرایش در {farm}", reply_markup=edit_keyboard())
        context.bot.send_message(
            chat_id=user.id,
            text=f"انتخاب مولفه برای ویرایش در {farm}",
            reply_markup=edit_keyboard_reply(),
        )
        return EDIT_FARM
    except KeyError:
        logger.info(f"key {farm} doesn't exist.")
        return ConversationHandler.END

def edit_farm(update: Update, context: CallbackContext):
    user_data = context.user_data
    user = update.effective_user
    message_id = update.effective_message.message_id
    # attr = update.callback_query.data
    attr = update.message.text
    if attr == "بازگشت به لیست باغ ها":
        db.log_activity(user.id, "back")
        # context.bot.edit_message_text(chat_id=user.id, message_id=message_id, text="یکی از باغ های خود را انتخاب کنید",
        #                                reply_markup=farms_list_reply(db, user.id))
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    if attr == "تغییر محصول":
        db.log_activity(user.id, "chose edit product")
        user_data["attr"] = attr
        context.bot.send_message(
            chat_id=user.id,
            text="لطفا محصول جدید باغ را انتخاب کنید",
            reply_markup=get_product_keyboard(),
        )
        return HANDLE_EDIT
    elif attr == "تغییر استان":
        db.log_activity(user.id, "chose edit province")
        user_data["attr"] = attr
        context.bot.send_message(
            chat_id=user.id,
            text="لطفا استان جدید باغ را انتخاب کنید",
            reply_markup=get_province_keyboard(),
        )
        return HANDLE_EDIT
    elif attr == "تغییر شهرستان":
        db.log_activity(user.id, "chose edit city")
        user_data["attr"] = attr
        context.bot.send_message(chat_id=user.id, text="لطفا شهر جدید باغ را وارد کنید", reply_markup=back_button())
        return HANDLE_EDIT
    elif attr == "تغییر روستا":
        db.log_activity(user.id, "chose edit village")
        user_data["attr"] = attr
        context.bot.send_message(
            chat_id=user.id, text="لطفا روستای جدید باغ را وارد کنید", reply_markup=back_button()
        )
        return HANDLE_EDIT
    elif attr == "تغییر مساحت":
        db.log_activity(user.id, "chose edit area")
        user_data["attr"] = attr
        context.bot.send_message(
            chat_id=user.id, text="لطفا مساحت جدید باغ را وارد کنید", reply_markup=back_button()
        )
        return HANDLE_EDIT
    elif attr == "تغییر موقعیت":
        db.log_activity(user.id, "chose edit location")
        user_data["attr"] = attr
        text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
        keyboard = [
            [KeyboardButton("ارسال لینک آدرس (گوگل مپ یا نشان)")],
            [
                KeyboardButton(
                    "ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True
                )
            ],
            [KeyboardButton("از نقشه داخل تلگرام انتخاب میکنم")],
            [KeyboardButton("بازگشت")]
        ]
        context.bot.send_message(
            chat_id=user.id,
            text=text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return HANDLE_EDIT

def handle_edit(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    attr = user_data["attr"]
    farm = user_data["selected_farm"]
    user_farms = db.get_farms(user.id)
    ## handle the new value of attr
    if attr == "تغییر محصول":
        new_product = update.message.text
        if new_product == "بازگشت":
            context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_product or new_product not in PRODUCTS:
            db.log_activity(user.id, "error - edit product")
            update.message.reply_text(
                "لطفا محصول جدید باغ را انتخاب کنید",
                reply_markup=get_product_keyboard(),
            )
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.product", new_product)
        reply_text = f"محصول جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit product")
        context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر استان":
        new_province = update.message.text
        if new_province == "بازگشت":
            context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_province or new_province not in PROVINCES:
            db.log_activity(user.id, "error edit province")
            update.message.reply_text(
                "لطفا استان جدید باغ را انتخاب کنید",
                reply_markup=get_province_keyboard(),
            )
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.province", new_province)
        reply_text = f"استان جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit province")
        context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر شهرستان":
        new_city = update.message.text
        if new_city == "بازگشت":
            context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_city:
            db.log_activity(user.id, "error - edit city")
            update.message.reply_text("لطفا شهرستان جدید باغ را انتخاب کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.city", new_city)
        reply_text = f"شهرستان جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit city")
        context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر روستا":
        new_village = update.message.text
        if new_village == "بازگشت":
            context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_village:
            db.log_activity(user.id, "error - edit village")
            update.message.reply_text("لطفا روستای جدید باغ را انتخاب کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.village", new_village)
        reply_text = f"روستای جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit village")
        context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر مساحت":
        new_area = update.message.text
        if new_area == "بازگشت":
            context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_area:
            db.log_activity(user.id, "error - edit area")
            update.message.reply_text("لطفا مساحت جدید باغ را انتخاب کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.area", new_area)
        reply_text = f"مساحت جدید {farm} با موفقیت ثبت شد."
        db.log_activity(user.id, "finish edit area")
        context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر موقعیت":
        new_location = update.message.location
        text = update.message.text
        if text == "بازگشت":
            context.bot.send_message(chat_id=user.id, text = "انتخاب مولفه برای ویرایش", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if text == "ارسال لینک آدرس (گوگل مپ یا نشان)":
            db.log_activity(user.id, "chose to edit location with link")
            update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
            return HANDLE_EDIT_LINK
        if new_location:
            logger.info(f"{update.effective_user.id} chose: ersal new_location online")
            db.set_user_attribute(
                user.id, f"farms.{farm}.location.longitude", new_location.longitude
            )
            db.set_user_attribute(
                user.id, f"farms.{farm}.location.latitude", new_location.latitude
            )
            reply_text = f"موقعیت جدید {farm} با موفقیت ثبت شد."
            db.log_activity(user.id, "finish edit location")
            context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
            )
            return ConversationHandler.END
        if not new_location and text != "از نقشه داخل تلگرام انتخاب میکنم":
            logger.info(
                f"{update.effective_user.id} didn't send new_location successfully"
            )
            reply_text = "ارسال موقعیت جدید باغ با موفقیت انجام نشد."
            db.log_activity(user.id, "error - edit location")
            context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=edit_keyboard_reply()
            )
            return EDIT_FARM
        elif text == "از نقشه داخل تلگرام انتخاب میکنم":
            db.log_activity(user.id, "chose to send location from map")
            logger.info(
                f"{update.effective_user.id} chose: az google map entekhab mikonam"
            )
            reply_text = """
مطابق فیلم راهنما موقعیت جدید باغ خود را انتخاب کنید
    
👉  https://t.me/agriweath/2
            """
            context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=ReplyKeyboardRemove()
            )
            return HANDLE_EDIT


def handle_edit_link(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    text = update.message.text
    if not text:
        db.log_activity(user.id, "error - no location link")
        update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
        return HANDLE_EDIT_LINK
    elif text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
        keyboard = [
        [KeyboardButton("ارسال لینک آدرس (گوگل مپ یا نشان)")],
        [
            KeyboardButton(
                "ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True
            )
        ],
        [KeyboardButton("از نقشه داخل تلگرام انتخاب میکنم")],
        [KeyboardButton("بازگشت")]
        ]
        update.message.reply_text(
            reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return HANDLE_EDIT
    reply_text = "ارسال لینک آدرس باغ با موفقیت انجام شد."
    db.log_activity(user.id, "finish edit location with link")
    update.message.reply_text(reply_text, reply_markup=start_keyboard())
    for admin in ADMIN_LIST:
        context.bot.send_message(chat_id=admin, text=f"user {user.id} sent us a link for\nname:{user_data['selected_farm']}\n{text}")
    return ConversationHandler.END
    
def delete_farm_keyboard(update: Update, context: CallbackContext):
    user = update.effective_user
    db.log_activity(user.id, "start delete process")
    user_farms = db.get_farms(user.id)
    if user_farms:
        update.message.reply_text(
            "یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    else:
        update.message.reply_text(
            "شما هنوز باغی ثبت نکرده اید", reply_markup=start_keyboard()
        )
        return ConversationHandler.END

def confirm_delete(update: Update, context: CallbackContext):
    user_data = context.user_data
    farm = update.message.text
    user_data["farm_to_delete"] = farm
    user = update.effective_user
    user_farms = db.get_farms(user.id)
    user_farms_names = list(db.get_farms(user.id).keys())
    if farm not in user_farms_names and farm != "↩️ بازگشت":
        db.log_activity(user.id, "error - wrong farm to delete")
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    if farm == "↩️ بازگشت":
        db.log_activity(user.id, "back")
        context.bot.send_message(
            chat_id=user.id, text="عملیات کنسل شد!", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm to delete")
    location = user_farms.get(farm)["location"]
    text = f"""
آیا از حذف <b>{farm}</b> با مشخصات زیر اطمینان دارید؟
محصول باغ: {user_farms[farm].get("product")}
مساحت: {user_farms[farm].get("area")}
آدرس انتخاب شده ⬇️
"""
    context.bot.send_message(chat_id=user.id, text=text, parse_mode=ParseMode.HTML)

    if location and location != {}:
        context.bot.send_location(
            chat_id=user.id,
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            reply_markup=conf_del_keyboard(),
        )
        return DELETE_FARM
    else:
        context.bot.send_message(
            chat_id=user.id,
            text=f"موقعیت <{farm}> ثبت نشده است. ",
            reply_markup=conf_del_keyboard(),
        )
        return DELETE_FARM

def delete_farm(update: Update, context: CallbackContext):
    user_data = context.user_data
    user = update.effective_user
    farm = user_data["farm_to_delete"]
    answer = update.message.text
    acceptable = ["بله", "خیر", "بازگشت"]
    if answer not in acceptable:
        db.log_activity(user.id, "error - wrong delete confirmation")
        context.bot.send_message(
            chat_id=user.id, text="عملیات موفق نبود", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif answer == "بازگشت":
        db.log_activity(user.id, "back")
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    elif answer == "خیر":
        db.log_activity(user.id, "stopped delete")
        context.bot.send_message(
            chat_id=user.id, text="عملیات لغو شد", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif answer == "بله":
        db.log_activity(user.id, "confirmed delete")
        try:
            db.user_collection.update_one(
                {"_id": user.id}, {"$unset": {f"farms.{farm}": ""}}
            )
            text = f"{farm} با موفقیت حذف شد."
            context.bot.send_message(
                chat_id=user.id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=start_keyboard(),
            )
            return ConversationHandler.END
        except KeyError:
            logger.info(f"DELETE: key {farm} doesn't exist for user {user.id}.")
            return ConversationHandler.END

# Function to send personalized scheduled messages
def send_location_guide(update: Update, context: CallbackContext, bot: Bot):
    # Retrieve all user data
    ids = db.user_collection.distinct("_id")
    i = 0
    for user_id in ids:
        chat = context.bot.getChat(user_id)
        username = chat.username
        # user_data[user_id]['username'] = username
        # if not "location" in user_data[user_id]:
        message = """
باغدار عزیز برای ارسال توصیه‌های هواشناسی، به لوکیشن (موقعیت جغرافیایی) باغ شما نیاز داریم.
لطفا با ارسال لوکیشن باغ، ثبت نام خود را از طریق /start تکمیل کنید.

برای راهنمایی به @agriiadmin پیام دهید.
                """
        try:
            bot.send_message(
                user_id, message
            )  ##, parse_mode=telegram.ParseMode.MARKDOWN_V2)
            db.log_new_message(user_id, message)
            # user_data[user_id]["blocked"] = False
            # user_data[user_id]['send-location-date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            i += 1

        except Unauthorized:
            logger.info(f"user {user_id} blocked the bot")
            db.set_user_attribute(user_id, "blocked", True)
            # user_data[user_id]["blocked"] = True
            # user_data[user_id]['block-date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"send_location_data succeeded for {i} out of {len(ids)} users.")
    # with open("location_guide_data.pickle", "wb") as job_data:
    #     pickle.dump(user_data, job_data)


def error_handler(update: Update, context: CallbackContext):
    logger.error('Update "%s" caused error "%s"', update, context.error)


# START OF REGISTER CONVERSATION
def register(update: Update, context: CallbackContext):
    user = update.effective_user
    db.log_activity(user.id, "start register")
    if db.check_if_user_is_registered(user_id=user.id):
        update.message.reply_text(
            "شما قبلا ثبت نام کرده‌اید. می‌توانید با استفاده از /add به ثبت باغ‌های خود اقدام کنید"
        )
        return ConversationHandler.END
    update.message.reply_text(
        "لطفا نام و نام خانوادگی خود را وارد کنید", reply_markup=ReplyKeyboardRemove()
    )
    return ASK_PHONE


def ask_phone(update: Update, context: CallbackContext):
    user = update.effective_user
    db.log_activity(user.id, "enter name")
    user_data = context.user_data
    # Get the answer to the area question
    if not update.message.text or update.message.text == "/start":
        update.message.reply_text("لطفا نام و نام خانوادگی خود را وارد کنید")
        return ASK_PHONE
    name = update.message.text.strip()
    user_data["name"] = name
    db.set_user_attribute(user_id=user.id, key="name", value=name)
    # db.set_user_attribute(user.id, 'products', user_data['product'], array=True)
    # db.set_user_attribute(user.id, 'provinces', user_data['province'], array=True)
    # db.set_user_attribute(user.id, 'cities', user_data['city'], array=True)
    # db.set_user_attribute(user.id, 'villages', user_data['village'], array=True)
    # db.set_user_attribute(user.id, 'areas', user_data['area'], array=True)
    update.message.reply_text("لطفا شماره تلفن خود را وارد کنید:")
    return HANDLE_PHONE


def handle_phone(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    # Get the answer to the area question
    phone = update.message.text
    if not phone or len(phone) != 11 or phone == "/start":
        update.message.reply_text("لطفا شماره تلفن خود را وارد کنید:")
        return HANDLE_PHONE
    db.log_activity(user.id, "entered phone")
    user_data["phone"] = phone
    db.set_user_attribute(user_id=user.id, key="phone-number", value=phone)
    reply_text = """
از ثبت نام شما در بات هواشناسی کشاورزی متشکریم.
لطفا با استفاده از /add نسبت به ثبت باغ‌های خود اقدام کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
شماره ثابت: 02164063399
    """
    update.message.reply_text(reply_text)
    return ConversationHandler.END


# START OF ADD_FARM CONVERSATION
def add(update: Update, context: CallbackContext):
    user = update.effective_user
    db.log_activity(user.id, "start add farm")
    if not db.check_if_user_is_registered(user_id=user.id):
        update.message.reply_text(
            "لطفا پیش از افزودن باغ از طریق /register ثبت نام کنید",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END
    reply_text = """
لطفا برای تشخیص این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
    update.message.reply_text(reply_text, reply_markup=back_button())
    #
    return ASK_PRODUCT


def ask_product(
    update: Update, context: CallbackContext
):  # HANDLES THE NAME RECEIVED FROM USER
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        update.message.reply_text("عمیلات لغو شد", reply_markup=start_keyboard())
        return ConversationHandler.END

    if not update.message.text or update.message.text == "/start":
        db.log_activity(user.id, "error - no name received")
        reply_text = """
لطفا برای دسترسی ساده‌تر به این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
        update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_PRODUCT
    elif db.user_collection.find_one({"_id": user.id}).get("farms"):
        used_farm_names = db.user_collection.find_one({"_id": user.id})["farms"].keys()
        if update.message.text in used_farm_names:
            db.log_activity(user.id, "error - chose same name")
            reply_text = (
                "شما قبلا از این نام استفاده کرده‌اید. لطفا یک نام جدید انتخاب کنید."
            )
            update.message.reply_text(reply_text, reply_markup=back_button())
            return ASK_PRODUCT
    name = update.message.text.strip()
    db.log_activity(user.id, "chose name")
    user_data["farm_name"] = name
    # db.set_user_attribute(user.id, "name", name)
    # db.set_user_attribute(user.id, "finished-sign-up", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    # logger.info(f"{update.effective_user.username} (id: {update.effective_user.id}) Finished sign up.")
    update.message.reply_text(
        "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
    )
    return ASK_PROVINCE


def ask_province(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = """
لطفا برای تشخیص این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
        update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_PRODUCT
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PRODUCTS:
        db.log_activity(user.id, "error - chose wrong product")
        update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
        )
        return ASK_PROVINCE
    product = update.message.text.strip()
    user_data["product"] = product
    db.log_activity(user.id, "chose product")
    update.message.reply_text(
        "لطفا استان محل باغ خود را انتخاب کنید:", reply_markup=get_province_keyboard()
    )
    return ASK_CITY


def ask_city(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
        )
        return ASK_PROVINCE
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PROVINCES:
        db.log_activity(user.id, "error - chose wrong province")
        update.message.reply_text(
            "لطفا استان محل باغ خود را انتخاب کنید:",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    province = update.message.text.strip()
    user_data["province"] = province
    db.log_activity(user.id, "chose province")
    update.message.reply_text(
        "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
    )
    return ASK_VILLAGE


def ask_village(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        update.message.reply_text(
            "لطفا استان محل باغ خود را انتخاب کنید:",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    # Get the answer to the province question
    if not update.message.text or update.message.text == "/start":
        db.log_activity(user.id, "error - city")
        update.message.reply_text(
            "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_VILLAGE
    city = update.message.text.strip()
    user_data["city"] = city
    db.log_activity(user.id, "entered city")
    update.message.reply_text(
        "لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button()
    )
    return ASK_AREA


def ask_area(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        update.message.reply_text(
            "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_VILLAGE
    # Get the answer to the village question
    if not update.message.text or update.message.text == "/start":
        db.log_activity(user.id, "error - village")
        update.message.reply_text(
            "لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_AREA
    village = update.message.text.strip()
    user_data["village"] = village
    db.log_activity(user.id, "entered village")
    update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
    return ASK_LOCATION


def ask_location(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        update.message.reply_text("لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button())
        return ASK_AREA
    # Get the answer to the phone number question
    if not update.message.text or update.message.text == "/start":
        db.log_activity(user.id, "error - area")
        update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
        return ASK_LOCATION
    area = update.message.text.strip()
    user_data["area"] = area
    db.log_activity(user.id, "entered area")
    reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
    keyboard = [
        [KeyboardButton("ارسال لینک آدرس (گوگل مپ یا نشان)")],
        [
            KeyboardButton(
                "ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True
            )
        ],
        [KeyboardButton("از نقشه داخل تلگرام انتخاب میکنم")],
        [KeyboardButton("بازگشت")]
    ]
    update.message.reply_text(
        reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HANDLE_LOCATION


def handle_location(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
        return ASK_LOCATION
    if update.message.text == "ارسال لینک آدرس (گوگل مپ یا نشان)":
        db.log_activity(user.id, "chose location link")
        update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
        return HANDLE_LINK
            

    farm_name = user_data["farm_name"]
    farm_product = user_data["product"]
    farm_province = user_data["province"]
    farm_city = user_data["city"]
    farm_village = user_data["village"]
    farm_area = user_data["area"]

    # Get the user's location
    location = update.message.location
    text = update.message.text
    if location:
        db.log_activity(user.id, "sent location")
        logger.info(f"{update.effective_user.id} chose: ersal location online")
        user_data["location"] = {
            "latitude": location.latitude,
            "longitude": location.longitude,
        }
        farm_location = user_data["location"]
        new_farm_dict = {
            "product": farm_product,
            "province": farm_province,
            "city": farm_city,
            "village": farm_village,
            "area": farm_area,
            "location": farm_location,
            "location-method": "User sent location"
        }
        db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
        db.log_activity(user.id, "finish add farm - gave location")
        reply_text = f"""
باغ شما با نام <{farm_name}> با موفقیت ثبت شد.
توصیه‌های مرتبط با شرایط آب‌و‌هوایی از روزهای آینده برای شما ارسال خواهد  
برای ویرایش اطلاعات باغ از /edit استفاده کنید.
"""
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END
    if not location and text != "از نقشه داخل تلگرام انتخاب میکنم":
        db.log_activity(user.id, "error - location")
        logger.info(f"{update.effective_user.id} didn't send location successfully")
        reply_text = "ارسال موقعیت باغ با موفقیت انجام نشد. می توانید از طریق ویرایش باغ موقعیت آن را ثبت کنید"
        user_data["location"] = {
            "latitude": None,
            "longitude": None,
        }
        farm_location = user_data["location"]
        new_farm_dict = {
            "product": farm_product,
            "province": farm_province,
            "city": farm_city,
            "village": farm_village,
            "area": farm_area,
            "location": farm_location,
            "location-method": "Unsuccessful"
        }
        db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
        db.log_activity(user.id, "finish add farm - no location")
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END
    elif text == "از نقشه داخل تلگرام انتخاب میکنم":
        db.log_activity(user.id, "chose to send location from map")
        logger.info(f"{update.effective_user.id} chose: az google map entekhab mikonam")
        reply_text = """
        مطابق فیلم راهنما موقعیت لوکیشن باغ خود را انتخاب کنید
        
        👉  https://t.me/agriweath/2
        """
        update.message.reply_text(reply_text, reply_markup=ReplyKeyboardRemove())
        return HANDLE_LOCATION

def handle_link(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    text = update.message.text
    farm_name = user_data["farm_name"]
    farm_product = user_data["product"]
    farm_province = user_data["province"]
    farm_city = user_data["city"]
    farm_village = user_data["village"]
    farm_area = user_data["area"]
    if not text:
        db.log_activity(user.id, "error - no location link")
        update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
        return HANDLE_LINK
    elif text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
        keyboard = [
        [KeyboardButton("ارسال لینک آدرس (گوگل مپ یا نشان)")],
        [
            KeyboardButton(
                "ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True
            )
        ],
        [KeyboardButton("از نقشه داخل تلگرام انتخاب میکنم")],
        [KeyboardButton("بازگشت")]
        ]
        update.message.reply_text(
            reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return HANDLE_LOCATION
    else:
        db.log_activity(user.id, "sent location link")
        reply_text = "ارسال لینک آدرس باغ با موفقیت انجام شد. لطفا تا بررسی ادمین منتظر بمانید. از شکیبایی شما سپاسگزاریم."
        user_data["location"] = {
            "latitude": None,
            "longitude": None,
        }
        farm_location = user_data["location"]
        new_farm_dict = {
            "product": farm_product,
            "province": farm_province,
            "city": farm_city,
            "village": farm_village,
            "area": farm_area,
            "location": farm_location,
            "location-method": "Link"
        }
        db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
        db.log_activity(user.id, "finish add farm with location link")
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        for admin in ADMIN_LIST:
            context.bot.send_message(chat_id=admin, text=f"user {user.id} sent us a link for\nname:{farm_name}\n{text}")
        return ConversationHandler.END

# START OF REQUEST WEATHER CONVERSATION
def req_weather_data(update: Update, context: CallbackContext):
    user = update.effective_user
    db.log_activity(user.id, "request weather")
    user_farms = db.get_farms(user.id)
    if user_farms:
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return RECV_WEATHER
    else:
        db.log_activity(user.id, "error - no farm for weather report")
        context.bot.send_message(
            chat_id=user.id,
            text="شما هنوز باغی ثبت نکرده اید",
            reply_markup=start_keyboard(),
        )
        return ConversationHandler.END

def recv_weather(update: Update, context: CallbackContext):
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
        update.message.reply_text("عملیات لغو شد", reply_markup=start_keyboard())
        return ConversationHandler.END
    if farm not in list(user_farms.keys()):
        db.log_activity(user.id, "error - chose farm for weather report")
        update.message.reply_text("لطفا دوباره تلاش کنید. نام باغ اشتباه بود", reply_markup=start_keyboard())
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm for weather report")
    longitude = user_farms[farm]["location"]["longitude"]
    latitude = user_farms[farm]["location"]["latitude"]
    
    if longitude is not None:
        try:
            if datetime.time(7, 0).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(20, 30).strftime("%H%M"):    
                weather_data = gpd.read_file(f"data/pesteh{today}_1.geojson")
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
وضعیت آب و هوای باغ شما با نام <{farm}> بدین صورت خواهد بود
"""
                    table([jtoday, jday2, jday3, jday4], tmin_values, tmax_values, rh_values, spd_values, rain_values)
                    with open('table.png', 'rb') as image_file:
                        context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=start_keyboard())
                    db.log_activity(user.id, "received 2 weather reports")
                    return ConversationHandler.END
                else:
                    context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات هواشناسی باغ شما در حال حاضر موجود نیست", reply_markup=start_keyboard())
                    return ConversationHandler.END
            else:
                weather_data = gpd.read_file(f"data/pesteh{yesterday}_1.geojson")
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
وضعیت آب و هوای باغ شما با نام <{farm}> بدین صورت خواهد بود
"""
                    table([jday2, jday3, jday4], tmin_values[1:], tmax_values[1:], rh_values[1:], spd_values[1:], rain_values[1:])
                    with open('table.png', 'rb') as image_file:
                        context.bot.send_photo(chat_id=user.id, photo=image_file, caption=caption, reply_markup=start_keyboard())
                    # context.bot.send_message(chat_id=user.id, text=weather_today, reply_markup=start_keyboard())
                    db.log_activity(user.id, "received 1 weather reports")
                    return ConversationHandler.END
                else:
                    context.bot.send_message(chat_id=user.id, text="متاسفانه اطلاعات هواشناسی باغ شما در حال حاضر موجود نیست", reply_markup=start_keyboard())
                    return ConversationHandler.END
        except DriverError:
            logger.info(f"{user.id} requested today's weather. pesteh{today}_1.geojson was not found!")
        finally:
            os.system("rm table.png")
    else:
        context.bot.send_message(chat_id=user.id, text="موقعیت باغ شما ثبت نشده است. لظفا پیش از درخواست اطلاعات هواشناسی نسبت به ثبت موققعیت اقدام فرمایید.",
                                 reply_markup=start_keyboard())
        return ConversationHandler.END
 
def main():
    updater = Updater(
        TOKEN, use_context=True
    )  # , request_kwargs={'proxy_url': PROXY_URL})

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("register", register))
    # dp.add_handler(CommandHandler("add", add))
    # Add handlers to the dispatcher
    register_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex("✍️ ثبت نام"), register)],
        states={
            ASK_PHONE: [MessageHandler(Filters.text & ~Filters.command, ask_phone)],
            HANDLE_PHONE: [
                MessageHandler(Filters.text & ~Filters.command, handle_phone)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dp.add_handler(register_conv)
    
    weather_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex("🌦 درخواست اطلاعات هواشناسی"), req_weather_data)],
        states={
            RECV_WEATHER: [MessageHandler(Filters.text , recv_weather)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dp.add_handler(weather_conv)

    add_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex("➕ اضافه کردن باغ"), add)],
        states={
            ASK_PRODUCT: [MessageHandler(Filters.text, ask_product)],
            ASK_PROVINCE: [MessageHandler(Filters.text, ask_province)],
            ASK_CITY: [MessageHandler(Filters.text, ask_city)],
            ASK_VILLAGE: [MessageHandler(Filters.text, ask_village)],
            ASK_AREA: [MessageHandler(Filters.all, ask_area)],
            ASK_LOCATION: [MessageHandler(Filters.all, ask_location)],
            HANDLE_LOCATION: [MessageHandler(Filters.all, handle_location)],
            HANDLE_LINK: [MessageHandler(Filters.all, handle_link)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dp.add_handler(add_conv)

    view_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex("مشاهده"), view_farm_keyboard)],
        states={
            VIEW_FARM: [MessageHandler(Filters.all, view_farm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dp.add_handler(view_conv)

    edit_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex("ویرایش"), edit_farm_keyboard)],
        states={
            CHOOSE_ATTR: [MessageHandler(Filters.all, choose_attr_to_edit)],
            EDIT_FARM: [MessageHandler(Filters.all, edit_farm)],
            HANDLE_EDIT: [MessageHandler(Filters.all, handle_edit)],
            HANDLE_EDIT_LINK: [MessageHandler(Filters.all, handle_edit_link)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dp.add_handler(edit_conv)

    delete_conv = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex("🗑 حذف باغ ها"), delete_farm_keyboard)
        ],
        states={
            CONFIRM_DELETE: [MessageHandler(Filters.all, confirm_delete)],
            DELETE_FARM: [MessageHandler(Filters.all, delete_farm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dp.add_handler(delete_conv)

    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("send", send)],
        states={
            CHOOSE_RECEIVERS: [MessageHandler(Filters.all, choose_receivers)],
            BROADCAST: [MessageHandler(Filters.all, broadcast)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    set_location_handler = ConversationHandler(
        entry_points=[CommandHandler("set", set_loc)],
        states={
            ASK_FARM_NAME: [MessageHandler(Filters.all, ask_farm_name)],
            ASK_LONGITUDE: [MessageHandler(Filters.all, ask_longitude)],
            ASK_LATITUDE: [MessageHandler(Filters.all, ask_latitude)],
            HANDLE_LAT_LONG: [MessageHandler(Filters.all, handle_lat_long)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dp.add_handler(set_location_handler)
    dp.add_error_handler(error_handler)

    dp.add_handler(CommandHandler("stats", bot_stats))
    dp.add_handler(CallbackQueryHandler(button))

    dp.add_handler(broadcast_handler)
    # dp.add_handler(CommandHandler("stats", bot_stats, filters=Filters.user))
    # Start the bot
    updater.start_polling()

    # Schedule periodic messages
    job_queue = updater.job_queue
    
    job_queue.run_repeating(
        lambda context: get_member_count(context.bot, logger), interval=7200, first=60
    )
    job_queue.run_repeating(
        lambda context: send_todays_data(context.bot, ADMIN_LIST, logger),
        interval=datetime.timedelta(days=1),
        # first=10
        first=datetime.time(7, 30),
    )

    job_queue.run_once(lambda context: send_up_notice(context.bot, ADMIN_LIST, logger), when=5)
    # Run the bot until you press Ctrl-C or the process receives SIGINT, SIGTERM, or SIGABRT
    updater.idle()


if __name__ == "__main__":
    try:
        main()
    except NetworkError:
        logger.error("A network error was encountered!")
    except ConnectionRefusedError:
        logger.error("A ConnectionRefusedError was encountered!")
