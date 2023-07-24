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
from keyboards import (
    start_keyboard,
    stats_keyboard,
    get_product_keyboard,
    get_province_keyboard,
    return_keyboard,
    farms_list_reply,
    edit_keyboard_reply,
    farms_list_inline,
    conf_del_keyboard,
    back_button,
)

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
BROADCAST = 0
(
    ASK_PRODUCT,
    ASK_PROVINCE,
    ASK_CITY,
    ASK_VILLAGE,
    ASK_AREA,
    ASK_LOCATION,
    HANDLE_LOCATION,
) = range(7)
(
    EDIT_PROVINCE,
    EDIT_CITY,
    EDIT_VILLAGE,
    EDIT_AREA,
    EDIT_LOCATION,
    HANDLE_LOCATION_EDIT,
) = range(6)
ASK_PHONE, HANDLE_PHONE = range(2)
#  = range(1)
VIEW_FARM, CHOOSE_ATTR, EDIT_FARM, HANDLE_EDIT = range(4)
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
ADMIN_LIST = [103465015, 31583686]
CMD_LIST = [
    "تعداد اعضا",
    "تغییرات تعداد اعضا",
    "دانلود فایل اکسل",
    "ثبت نام ✍️",
    "اضافه کردن باغ ➕",
    "مشاهده باغ های ثبت شده 🖼",
    "ویرایش باغ های ثبت شده 📝",
]


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
برای دریافت توصیه‌های کاربردی هواشناسی از قبیل سرمازدگی، گرمازدگی و آفتاب‌سوختگی، خسارت باد، نیاز سرمایی و … با استفاده
از /register اقدام به ثبت نام کنید.
سپس با /add باغ خود را ثبت کنید.
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
تلفن ثابت: 02164063399
                """
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ASK_PROVINCE
    else:
        reply_text = """
راهنما:
ثبت نام در بات هواشناسی کشاورزی /register
اضافه کردن باغ  /add
ویرایش باغ‌های ثبت شده /edit
حذف باغ /delete
راه‌های ارتباطی با ما:
ادمین: @agriiadmin
شماره ثابت: 02164063399
        """
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END


# def handle_name_old(update: Update, context: CallbackContext):
#     user = update.effective_user
#     user_data = context.user_data
#     if not update.message.text or update.message.text=="/start":
#         update.message.reply_text("نام و نام خانودگی خود را وارد کنید:")
#         return HANDLE_NAME
#     name = update.message.text.strip()
#     user_data['name'] = name
#     db.set_user_attribute(user.id, "name", name)
#     db.set_user_attribute(user.id, "finished-sign-up", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
#     logger.info(f"{update.effective_user.username} (id: {update.effective_user.id}) Finished sign up.")
#     reply_text = """
# از ثبت نام شما در بات هواشناسی کشاورزی متشکریم.
# در روزهای آینده توصیه‌های کاربردی هواشناسی محصول پسته برای شما ارسال می‌شود.
# همراه ما باشید.
# راه‌های ارتباطی با ما:
# ادمین: @agriiadmin
# شماره ثابت: 02164063399
#     """
#     # persistence.update_user_data(user_id=update.effective_user.id, data = user_data)
#     update.message.reply_text(reply_text)
#     return ConversationHandler.END


def send(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in ADMIN_LIST:
        update.message.reply_text(
            "لطفا پیام مورد نظرتان را بنویسید یا برای لغو /cancel را بزنید:",
        )
        return BROADCAST
    else:
        return ConversationHandler.END


def broadcast(update: Update, context: CallbackContext):
    # user_data = db.user_collection.find()
    ids = db.user_collection.distinct("_id")
    i = 0
    receivers = []
    message = update.message.text
    if message == "/cancel":
        update.message.reply_text("عملیات کنسل شد!")
        return ConversationHandler.END
    if not message:
        update.message.reply_text(
            "لطفا پیام مورد نظرتان را بنویسید:",
        )
        return BROADCAST
    for user_id in ids:
        try:
            context.bot.send_message(user_id, message)
            username = db.user_collection.find_one({"_id": user_id})["username"]
            db.log_new_message(
                user_id=user_id,
                username=username,
                message=message,
                function="broadcast",
            )
            receivers.append(user_id)
            i += 1
        except Unauthorized:
            logger.error(f"user {user_id} blocked the bot")
        except BadRequest:
            logger.error(f"chat with {user_id} not found.")
    db.log_sent_messages(receivers, "broadcast")
    for id in ADMIN_LIST:
        context.bot.send_message(id, f"پیام برای {i} نفر از {len(ids)} نفر ارسال شد.")
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
        output_file = "member-data.xlsx"
        db.to_excel(output_file=output_file)
        doc = open(output_file, "rb")
        context.bot.send_document(chat_id=id, document=doc)
        doc.close()
        os.remove(output_file)


def get_member_count(bot: Bot):
    user_data = db.user_collection.distinct("_id")
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    member_count = len(user_data)
    db.log_member_changes(members=member_count, time=current_time)


def view_farm_keyboard(update: Update, context: CallbackContext):
    logger.info("ENTERED view_farm_keyboard")
    user = update.effective_user
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
    logger.info("ENTERED view_farm")
    farm = update.message.text
    # farm = f"view{farm}"
    logger.info(f"FARM: {farm}")
    user = update.effective_user
    user_farms = db.get_farms(user.id)
    user_farms_names = list(db.get_farms(user.id).keys())
    if farm not in user_farms_names and farm != "↩️ بازگشت":
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را ویرایش کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return VIEW_FARM
    if farm == "↩️ بازگشت":
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
    logger.info(f"message_id: {message_id}")
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
    except KeyError:
        logger.info(f"key {farm} doesn't exist.")
        return ConversationHandler.END


def edit_farm_keyboard(update: Update, context: CallbackContext):
    logger.info("ENTERED edit_farm_keyboard")
    user = update.effective_user
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
    logger.info("ENTERED edit_farm")
    # farm = update.callback_query.data
    farm = update.message.text

    user = update.effective_user
    user_data = context.user_data
    user_data["selected_farm"] = farm
    user_farms = list(db.get_farms(user.id).keys())
    if farm not in user_farms and farm != "↩️ بازگشت":
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را ویرایش کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    if farm == "↩️ بازگشت":
        context.bot.send_message(
            chat_id=user.id, text="عملیات کنسل شد!", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    message_id = update.effective_message.message_id
    logger.info(f"message_id: {message_id}")
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
    logger.info(attr)
    if attr == "بازگشت به لیست باغ ها":
        # context.bot.edit_message_text(chat_id=user.id, message_id=message_id, text="یکی از باغ های خود را انتخاب کنید",
        #                                reply_markup=farms_list_reply(db, user.id))
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    if attr == "تغییر محصول":
        user_data["attr"] = attr
        context.bot.send_message(
            chat_id=user.id,
            text="لطفا محصول جدید باغ را انتخاب کنید",
            reply_markup=get_product_keyboard(),
        )
        return HANDLE_EDIT
    elif attr == "تغییر استان":
        user_data["attr"] = attr
        context.bot.send_message(
            chat_id=user.id,
            text="لطفا استان جدید باغ را انتخاب کنید",
            reply_markup=get_province_keyboard(),
        )
        return HANDLE_EDIT
    elif attr == "تغییر شهرستان":
        user_data["attr"] = attr
        context.bot.send_message(chat_id=user.id, text="لطفا شهر جدید باغ را وارد کنید")
        return HANDLE_EDIT
    elif attr == "تغییر روستا":
        user_data["attr"] = attr
        context.bot.send_message(
            chat_id=user.id, text="لطفا روستای جدید باغ را وارد کنید"
        )
        return HANDLE_EDIT
    elif attr == "تغییر مساحت":
        user_data["attr"] = attr
        context.bot.send_message(
            chat_id=user.id, text="لطفا مساحت جدید باغ را وارد کنید"
        )
        return HANDLE_EDIT
    elif attr == "تغییر موقعیت":
        user_data["attr"] = attr
        text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
        keyboard = [
            [
                KeyboardButton(
                    "ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True
                )
            ],
            [KeyboardButton("از نقشه (گوگل مپ) انتخاب میکنم")],
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
        if not new_product or new_product not in PRODUCTS:
            update.message.reply_text(
                "لطفا محصول جدید باغ را انتخاب کنید",
                reply_markup=get_product_keyboard(),
            )
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.product", new_product)
        reply_text = f"محصول جدید {farm} با موفقیت ثبت شد."
        context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر استان":
        new_province = update.message.text
        if not new_province or new_province not in PROVINCES:
            update.message.reply_text(
                "لطفا استان جدید باغ را انتخاب کنید",
                reply_markup=get_province_keyboard(),
            )
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.province", new_province)
        reply_text = f"استان جدید {farm} با موفقیت ثبت شد."
        context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر شهرستان":
        new_city = update.message.text
        if not new_city:
            update.message.reply_text("لطفا شهرستان جدید باغ را انتخاب کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.city", new_city)
        reply_text = f"شهرستان جدید {farm} با موفقیت ثبت شد."
        context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر روستا":
        new_village = update.message.text
        if not new_village:
            update.message.reply_text("لطفا روستای جدید باغ را انتخاب کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.village", new_village)
        reply_text = f"روستای جدید {farm} با موفقیت ثبت شد."
        context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر مساحت":
        new_area = update.message.text
        if not new_area:
            update.message.reply_text("لطفا مساحت جدید باغ را انتخاب کنید")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.area", new_area)
        reply_text = f"مساحت جدید {farm} با موفقیت ثبت شد."
        context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif attr == "تغییر موقعیت":
        logger.info(f"ATTRIBBUTE TO EDIT: {attr}")
        new_location = update.message.location
        text = update.message.text
        logger.info(f"TEXT: {text} & LOCATION:{new_location}")
        if new_location:
            logger.info(f"{update.effective_user.id} chose: ersal new_location online")
            db.set_user_attribute(
                user.id, f"farms.{farm}.location.longitude", new_location.longitude
            )
            db.set_user_attribute(
                user.id, f"farms.{farm}.location.latitude", new_location.latitude
            )
            reply_text = f"موقعیت جدید {farm} با موفقیت ثبت شد."
            context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=start_keyboard()
            )
            return ConversationHandler.END
        if not new_location and text != "از نقشه (گوگل مپ) انتخاب میکنم":
            logger.info(
                f"{update.effective_user.id} didn't send new_location successfully"
            )
            reply_text = "ارسال موقعیت جدید باغ با موفقیت انجام نشد."

            context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=edit_keyboard_reply()
            )
            return EDIT_FARM
        elif text == "از نقشه (گوگل مپ) انتخاب میکنم":
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


def delete_farm_keyboard(update: Update, context: CallbackContext):
    logger.info("ENTERED delete_farm_keyboard")
    user = update.effective_user
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
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    if farm == "↩️ بازگشت":
        context.bot.send_message(
            chat_id=user.id, text="عملیات کنسل شد!", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    location = user_farms.get(farm)["location"]
    logger.info(location)
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
            text=f"متاسفانه موقعیت <{farm}> ثبت نشده است. ",
            reply_markup=conf_del_keyboard(),
        )
        return DELETE_FARM


def delete_farm(update: Update, context: CallbackContext):
    logger.info("ENTER delete_farm")
    user_data = context.user_data
    user = update.effective_user
    farm = user_data["farm_to_delete"]
    answer = update.message.text
    acceptable = ["بله", "خیر", "بازگشت"]
    if answer not in acceptable:
        context.bot.send_message(
            chat_id=user.id, text="عملیات موفق نبود", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif answer == "بازگشت":
        context.bot.send_message(
            chat_id=user.id,
            text="یکی از باغ های خود را انتخاب کنید",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CONFIRM_DELETE
    elif answer == "خیر":
        context.bot.send_message(
            chat_id=user.id, text="عملیات لغو شد", reply_markup=start_keyboard()
        )
        return ConversationHandler.END
    elif answer == "بله":
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


def send_advice_to_users(bot: Bot):
    ids = db.user_collection.distinct("_id")
    current_day = datetime.datetime.now().strftime("%Y%m%d")
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
                    advise = advise_data.iloc[idx_min_dist]["Adivse"]
                    message = f"""
باغدار عزیز 
توصیه زیر با توجه به وضعیت آب و هوایی امروز باغ شما ارسال می‌شود:

{advise}
                    """
                    # logger.info(message)
                    if pd.isna(advise):
                        logger.info(
                            f"No advice for user {id} with location (long:{longitude}, lat:{latitude}). Closest point in advise data "
                            f"is index:{idx_min_dist} - {advise_data.iloc[idx_min_dist]['geometry']}"
                        )
                    if not pd.isna(advise):
                        try:
                            # bot.send_message(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                            bot.send_message(chat_id=id, text=message)
                            username = db.user_collection.find_one({"_id": id})[
                                "username"
                            ]
                            db.log_new_message(
                                user_id=id,
                                username=username,
                                message=message,
                                function="send_advice",
                            )
                            logger.info(f"sent recommendation to {id}")
                            message_count += 1
                            receiver_id.append(id)
                            # bot.send_location(chat_id=id, location=Location(latitude=latitude, longitude=longitude))
                        except Unauthorized:
                            db.set_user_attribute(id, "blocked", True)
                            logger.info(f"user:{id} has blocked the bot!")
                            for admin in ADMIN_LIST:
                                bot.send_message(
                                    chat_id=admin,
                                    text=f"user: {id} has blocked the bot!",
                                )
                        except BadRequest:
                            logger.info(f"user:{id} chat was not found!")
                else:
                    logger.info(
                        f"user's location: ({longitude},{latitude}) | closest point in dataset: ({closest_coords[0]},{closest_coords[1]}) | distance: {point.distance(Point(closest_coords))}"
                    )
        db.log_sent_messages(receiver_id, "send_advice_to_users")
        logger.info(f"sent advice info to {message_count} people")
        for admin in ADMIN_LIST:
            bot.send_message(
                chat_id=admin, text=f"توصیه به {message_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=receiver_id)
    except DriverError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin,
                text=f"{time} file pesteh{current_day}.geojson was not found!",
            )
    except KeyError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin, text=f"key error in file pesteh{current_day}_1.geojson!"
            )

def send_todays_weather(bot: Bot):
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
                        for admin in ADMIN_LIST:
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
        for admin in ADMIN_LIST:
            bot.send_message(
                chat_id=admin, text=f"وضعیت آب و هوای {message_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=receiver_id)
    except DriverError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin,
                text=f"{time} file pesteh{current_day}_1.geojson was not found!",
            )
    except KeyError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin, text=f"key error in file pesteh{current_day}_1.geojson!"
            )

def send_tomorrows_weather(bot: Bot):
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
                        for admin in ADMIN_LIST:
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
        for admin in ADMIN_LIST:
            bot.send_message(
                chat_id=admin, text=f"وضعیت آب و هوای {message_count} کاربر ارسال شد"
            )
            bot.send_message(chat_id=admin, text=receiver_id)
    except DriverError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin,
                text=f"{time} file pesteh{current_day}_1.geojson was not found!",
            )
    except KeyError:
        for admin in ADMIN_LIST:
            time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            bot.send_message(
                chat_id=admin, text=f"key error in file pesteh{current_day}_1.geojson!"
            )

def send_up_notice(bot: Bot):
    for admin in ADMIN_LIST:
        bot.send_message(chat_id=admin, text="بات دوباره راه‌اندازی شد")

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
    if db.check_if_user_is_registered(user_id=user.id):
        update.message.reply_text(
            "شما قبلا ثبت نام کرده‌اید. می‌توانید با استفاده از /add به ثبت باغ‌های خود اقدام کنید"
        )
        return ConversationHandler.END
    logger.info("entered register")
    update.message.reply_text(
        "لطفا نام و نام خانوادگی خود را وارد کنید", reply_markup=ReplyKeyboardRemove()
    )
    return ASK_PHONE


def ask_phone(update: Update, context: CallbackContext):
    logger.info("entered ask_phone")
    user = update.effective_user
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
    logger.info(db.check_if_user_exists(user.id))
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
        update.message.reply_text("عمیلات لغو شد", reply_markup=start_keyboard())
        return ConversationHandler.END

    if not update.message.text or update.message.text == "/start":
        reply_text = """
لطفا برای دسترسی ساده‌تر به این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
        update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_PRODUCT
    elif db.user_collection.find_one({"_id": user.id}).get("farms"):
        used_farm_names = db.user_collection.find_one({"_id": user.id})["farms"].keys()
        if update.message.text in used_farm_names:
            reply_text = (
                "شما قبلا از این نام استفاده کرده‌اید. لطفا یک نام جدید انتخاب کنید."
            )
            update.message.reply_text(reply_text, reply_markup=back_button())
            return ASK_PRODUCT
    name = update.message.text.strip()

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
        reply_text = """
لطفا برای تشخیص این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
        update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_PRODUCT
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PRODUCTS:
        update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
        )
        return ASK_PROVINCE
    product = update.message.text.strip()
    user_data["product"] = product
    update.message.reply_text(
        "لطفا استان محل باغ خود را انتخاب کنید:", reply_markup=get_province_keyboard()
    )
    return ASK_CITY


def ask_city(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
        )
        return ASK_PROVINCE
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PROVINCES:
        update.message.reply_text(
            "لطفا استان محل باغ خود را انتخاب کنید:",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    province = update.message.text.strip()
    user_data["province"] = province
    update.message.reply_text(
        "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
    )
    return ASK_VILLAGE


def ask_village(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        update.message.reply_text(
            "لطفا استان محل باغ خود را انتخاب کنید:",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    # Get the answer to the province question
    if not update.message.text or update.message.text == "/start":
        update.message.reply_text(
            "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_VILLAGE
    city = update.message.text.strip()
    user_data["city"] = city
    update.message.reply_text(
        "لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button()
    )
    return ASK_AREA


def ask_area(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        update.message.reply_text(
            "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_VILLAGE
    # Get the answer to the village question
    if not update.message.text or update.message.text == "/start":
        update.message.reply_text(
            "لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_AREA
    village = update.message.text.strip()
    user_data["village"] = village
    update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
    return ASK_LOCATION


def ask_location(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        update.message.reply_text("لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button())
        return ASK_AREA
    # Get the answer to the phone number question
    if not update.message.text or update.message.text == "/start":
        update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
        return ASK_LOCATION
    area = update.message.text.strip()
    user_data["area"] = area
    reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را بفرستید."
    keyboard = [
        [
            KeyboardButton(
                "ارسال لوکیشن آنلاین (الان در باغ هستم)", request_location=True
            )
        ],
        [KeyboardButton("از نقشه (گوگل مپ) انتخاب میکنم")],
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
        update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
        return ASK_LOCATION

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
        }
        db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
        reply_text = f"""
باغ شما با نام <{farm_name}> با موفقیت ثبت شد.
توصیه‌های مرتبط با شرایط آب‌و‌هوایی از روزهای آینده برای شما ارسال خواهد  
برای ویرایش اطلاعات باغ از /edit استفاده کنید.
"""
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END
    if not location and text != "از نقشه (گوگل مپ) انتخاب میکنم":
        logger.info(f"{update.effective_user.id} didn't send location successfully")
        reply_text = "ارسال موقعیت باغ با موفقیت انجام نشد. می توانید از طریق ویرایش باغ موقعیت آن را ثبت کنید"
        user_data["location"] = {}
        farm_location = user_data["location"]
        new_farm_dict = {
            "product": farm_product,
            "province": farm_province,
            "city": farm_city,
            "village": farm_village,
            "area": farm_area,
            "location": farm_location,
        }
        db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
        update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END
    elif text == "از نقشه (گوگل مپ) انتخاب میکنم":
        logger.info(f"{update.effective_user.id} chose: az google map entekhab mikonam")
        reply_text = """
        مطابق فیلم راهنما موقعیت لوکیشن باغ خود را انتخاب کنید
        
        👉  https://t.me/agriweath/2
        """
        update.message.reply_text(reply_text, reply_markup=ReplyKeyboardRemove())
        return HANDLE_LOCATION

# START OF REQUEST WEATHER CONVERSATION
def req_weather_data(update: Update, context: CallbackContext):
    user = update.effective_user
    farms = db.get_farms(user.id)
    if farms:
        farm_names = list(farms.keys())
    today = datetime.datetime.now().strftime("%Y%m%d")
    try:
        data = gpd.read_file(f"pesteh{today}_1.geojson")
        
    except DriverError:
        logger.info(f"{user.id} requested today's weather. pesteh{today}_1.geojson was not found!")
        
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
    dp.add_handler(
        MessageHandler(
            Filters.regex("درخواست اطلاعات هواشناسی باغ ها 🌦"), send_todays_weather
        )
    )
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
            BROADCAST: [MessageHandler(Filters.all, broadcast)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # dp.add_error_handler(error_handler)

    dp.add_handler(CommandHandler("stats", bot_stats))
    dp.add_handler(CallbackQueryHandler(button))

    dp.add_handler(broadcast_handler)
    # dp.add_handler(CommandHandler("stats", bot_stats, filters=Filters.user))
    # Start the bot
    updater.start_polling()

    # Schedule periodic messages
    job_queue = updater.job_queue
    # job_queue.run_repeating(lambda context: send_scheduled_messages(updater, context, context.bot),
    #                         interval=datetime.timedelta(seconds=5).total_seconds())
    # job_queue.run_once(lambda context: send_location_guide(updater, context, context.bot), when=60)
    job_queue.run_repeating(
        lambda context: get_member_count(context.bot), interval=7200, first=60
    )
    job_queue.run_repeating(
        lambda context: send_todays_weather(context.bot),
        interval=datetime.timedelta(days=1),
        first=datetime.time(10, 25),
    )
    job_queue.run_repeating(
        lambda context: send_tomorrows_weather(context.bot),
        interval=datetime.timedelta(days=1),
        first=datetime.time(10, 26),
    )
    job_queue.run_repeating(
        lambda context: send_advice_to_users(context.bot),
        interval=datetime.timedelta(days=1),
        first=datetime.time(10, 27),
    )
    job_queue.run_once(lambda context: send_up_notice(context.bot), when=5)
    # Run the bot until you press Ctrl-C or the process receives SIGINT, SIGTERM, or SIGABRT
    updater.idle()


if __name__ == "__main__":
    try:
        main()
    except NetworkError:
        logger.error("A network error was encountered!")
    except ConnectionRefusedError:
        logger.error("A ConnectionRefusedError was encountered!")
