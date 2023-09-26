import logging
from logging.handlers import RotatingFileHandler
import datetime
from telegram import (
    KeyboardButton,
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.error import BadRequest, Forbidden
from telegram.constants import ParseMode 
import warnings

import database
from .regular_jobs import no_location_reminder
from .keyboards import (
    start_keyboard,
    manage_farms_keyboard,
    get_product_keyboard,
    get_province_keyboard,
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
logging.getLogger("httpx").setLevel(logging.WARNING)

# Constants for ConversationHandler states
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
PROVINCES = ["کرمان", "خراسان رضوی", "خراسان جنوبی", "یزد", "فارس", "سمنان", "مرکزی", "تهران", "اصفهان", "قزوین", "سیستان و بلوچستان", "قم", "سایر"]
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
ADMIN_LIST = [103465015, 31583686, 391763080, 216033407, 5827206050]
MENU_CMDS = ['✍️ ثبت نام', '📤 دعوت از دیگران', '🖼 مشاهده باغ ها', '➕ اضافه کردن باغ', '🗑 حذف باغ ها', '✏️ ویرایش باغ ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()


# START OF ADD_FARM CONVERSATION
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start add farm")
    if not db.check_if_user_is_registered(user_id=user.id):
        db.log_activity(user.id, "error - add farm", "not registered yet")
        await update.message.reply_text(
            "لطفا پیش از افزودن باغ از طریق /start ثبت نام کنید",
            reply_markup=start_keyboard(),
        )
        return ConversationHandler.END
    reply_text = """
لطفا برای تشخیص این باغ یک نام وارد کنید:
مثلا: باغ پسته
"""
    await update.message.reply_text(reply_text, reply_markup=back_button())
    #
    return ASK_PRODUCT

async def ask_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    logger.info(update.message.text)
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("عمیلات لغو شد", reply_markup=manage_farms_keyboard())
        return ConversationHandler.END
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - no name received")
        reply_text = """
لطفا برای دسترسی ساده‌تر به این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_PRODUCT
    if "." in update.message.text:
        db.log_activity(user.id, "error - chose name with .", f"{update.message.text}")
        reply_text = (
                "نام باغ نباید شامل <b>.</b> باشد. لطفا یک نام دیگر انتخاب کنید"
            )
        await update.message.reply_text(reply_text, reply_markup=back_button(), parse_mode=ParseMode.HTML)
        return ASK_PRODUCT
    elif db.user_collection.find_one({"_id": user.id}).get("farms"):
        used_farm_names = db.user_collection.find_one({"_id": user.id})["farms"].keys()
        if update.message.text in used_farm_names:
            db.log_activity(user.id, "error - chose same name", f"{update.message.text}")
            reply_text = (
                "شما قبلا از این نام استفاده کرده‌اید. لطفا یک نام جدید انتخاب کنید."
            )
            await update.message.reply_text(reply_text, reply_markup=back_button())
            return ASK_PRODUCT
    farm_name = update.message.text.strip()
    user_data["farm_name"] = farm_name
    db.log_activity(user.id, "chose name", f"{update.message.text}")
    new_farm_dict = {
        "product": None,
        "province": None,
        "city": None,
        "village": None,
        "area": None,
        "location": {"latitude": None, "longitude": None},
        "location-method": None
    }
    db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
    await update.message.reply_text(
        "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
    )
    return ASK_PROVINCE

async def ask_province(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = """
لطفا برای تشخیص این باغ یک نام انتخاب کنید:
مثلا باغ شماره 1
"""
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_PRODUCT
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PRODUCTS:
        db.log_activity(user.id, "error - chose wrong product", f"{update.message.text}")
        await update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
        )
        return ASK_PROVINCE
    product = update.message.text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.product", product)
    db.log_activity(user.id, "chose product", f"{product}")
    await update.message.reply_text(
        "لطفا استان محل باغ خود را انتخاب کنید:", reply_markup=get_province_keyboard()
    )
    return ASK_CITY

async def ask_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text(
            "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
        )
        return ASK_PROVINCE
    # Get the answer to the province question
    if not update.message.text or update.message.text not in PROVINCES:
        db.log_activity(user.id, "error - chose wrong province", f"{update.message.text}")
        await update.message.reply_text(
            "لطفا استان محل باغ خود را انتخاب کنید:",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    province = update.message.text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.province", province)
    db.log_activity(user.id, "chose province", f"{province}")
    await update.message.reply_text(
        "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
    )
    return ASK_VILLAGE

async def ask_village(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text(
            "لطفا استان محل باغ خود را انتخاب کنید:",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    # Get the answer to the province question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - city")
        await update.message.reply_text(
            "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_VILLAGE
    city = update.message.text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.city", city)
    db.log_activity(user.id, "entered city", f"{city}")
    await update.message.reply_text(
        "لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button()
    )
    return ASK_AREA

async def ask_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text(
            "لطفا شهرستان محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_VILLAGE
    # Get the answer to the village question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - village")
        await update.message.reply_text(
            "لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button()
        )
        return ASK_AREA
    village = update.message.text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.village", village)
    db.log_activity(user.id, "entered village", f"{village}")
    await update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
    return ASK_LOCATION

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("لطفا روستای محل باغ را وارد کنید:", reply_markup=back_button())
        return ASK_AREA
    # Get the answer to the phone number question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - area")
        await update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
        return ASK_LOCATION
    area = update.message.text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.area", area)
    db.log_activity(user.id, "entered area", f"{area}")
    reply_text = """
لطفا موقعیت باغ (لوکیشن باغ) خود را با انتخاب یکی از روش‌های زیر بفرستید.

🟢 ربات آباد از لوکیشن شما فقط در راستای ارسال توصیه ها استفاده می‌کند.
🟢 متاسفانه آباد امکان ارسال توصیه بدون داشتن لوکیشن باغ شما را ندارد.
🟢 در ارسال لوکیشن مشکل دارید ؟ جهت راهنمایی همین حالا به @agriiadmin پیام دهید.
    """
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
    await update.message.reply_text(
        reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HANDLE_LOCATION

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "بازگشت":
        db.log_activity(user.id, "back")
        await update.message.reply_text("لطفا سطح زیر کشت خود را به هکتار وارد کنید:", reply_markup=back_button())
        return ASK_LOCATION
    if update.message.text == "ارسال لینک آدرس (گوگل مپ یا نشان)":
        db.log_activity(user.id, "chose location link")
        await update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
        return HANDLE_LINK
            
    farm_name = user_data["farm_name"]

    # Get the user's location
    location = update.message.location
    text = update.message.text
    if location:
        db.log_activity(user.id, "sent location", f"long:{location['longitude']}, lat: {location['latitude']}")
        logger.info(f"{update.effective_user.id} chose: ersal location online")

        db.set_user_attribute(user.id, f"farms.{farm_name}.location.latitude", location.latitude)
        db.set_user_attribute(user.id, f"farms.{farm_name}.location.longitude", location.longitude)
        db.set_user_attribute(user.id, f"farms.{farm_name}.location-method", "User sent location")

        db.log_activity(user.id, "finished add farm - gave location", farm_name)
        reply_text = f"""
باغ شما با نام <{farm_name}> با موفقیت ثبت شد.
توصیه‌های مرتبط با شرایط آب‌و‌هوایی از روزهای آینده برای شما ارسال خواهد  شد.
برای ویرایش یا مشاهده اطلاعات باغ از گزینه‌های مرتبط در /start استفاده کنید.
"""
        await update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END
    if not location and text != "از نقشه داخل تلگرام انتخاب میکنم":
        db.log_activity(user.id, "error - location", text)
        logger.info(f"{update.effective_user.id} didn't send location successfully")
        reply_text = "ارسال موقعیت باغ با موفقیت انجام نشد. می توانید از طریق ویرایش باغ، موقعیت آن را ثبت کنید."
        
        db.set_user_attribute(user.id, f"farms.{farm_name}.location-method", "Unsuccessful")
        db.log_activity(user.id, "finish add farm - no location", farm_name)
        
        context.job_queue.run_once(no_location_reminder, when=datetime.timedelta(hours=1),chat_id=user.id, data=user.username)    
        await update.message.reply_text(reply_text, reply_markup=start_keyboard())
        return ConversationHandler.END
    elif text == "از نقشه داخل تلگرام انتخاب میکنم":
        db.log_activity(user.id, "chose to send location from map")
        logger.info(f"{update.effective_user.id} chose: az google map entekhab mikonam")
        reply_text = """
        مطابق فیلم راهنما موقعیت لوکیشن باغ خود را انتخاب کنید
        
        👉  https://t.me/agriweath/2
        """
        await update.message.reply_text(reply_text, reply_markup=ReplyKeyboardRemove())
        return HANDLE_LOCATION

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    text = update.message.text
    farm_name = user_data["farm_name"]
    if text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("عمیلات قبلی لغو شد. لطفا دوباره تلاش کنید.", reply_markup=start_keyboard())
        return ConversationHandler.END
    elif not text:
        db.log_activity(user.id, "error - no location link")
        await update.message.reply_text("لطفا لینک آدرس باغ خود را ارسال کنید.", reply_markup=back_button())
        return HANDLE_LINK
    elif text == "بازگشت":
        db.log_activity(user.id, "back")
        reply_text = "لطفا موقعیت باغ (لوکیشن باغ) خود را با انتخاب یکی از روش‌های زیر بفرستید."
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
        await update.message.reply_text(
            reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return HANDLE_LOCATION
    else:
        db.log_activity(user.id, "sent location link", text)
        reply_text = "ارسال لینک آدرس باغ با موفقیت انجام شد. لطفا تا بررسی ادمین منتظر بمانید. از شکیبایی شما سپاسگزاریم."
        db.set_user_attribute(user.id, f"farms.{farm_name}.location-method", "Link")
        db.log_activity(user.id, "finish add farm with location link", farm_name)
        context.job_queue.run_once(no_location_reminder, when=datetime.timedelta(hours=1), chat_id=user.id, data=user.username)    
        await update.message.reply_text(reply_text, reply_markup=start_keyboard())
        for admin in ADMIN_LIST:
            try:
                await context.bot.send_message(chat_id=admin, text=f"user {user.id} sent us a link for\nname:{farm_name}\n{text}")
            except BadRequest or Forbidden:
                logger.warning(f"admin {admin} has deleted the bot")
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات کنسل شد!")
    return ConversationHandler.END


add_farm_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("➕ اضافه کردن باغ"), add)],
        states={
            ASK_PRODUCT: [MessageHandler(filters.TEXT, ask_product)],
            ASK_PROVINCE: [MessageHandler(filters.TEXT, ask_province)],
            ASK_CITY: [MessageHandler(filters.TEXT, ask_city)],
            ASK_VILLAGE: [MessageHandler(filters.TEXT, ask_village)],
            ASK_AREA: [MessageHandler(filters.ALL, ask_area)],
            ASK_LOCATION: [MessageHandler(filters.ALL, ask_location)],
            HANDLE_LOCATION: [MessageHandler(filters.ALL, handle_location)],
            HANDLE_LINK: [MessageHandler(filters.ALL, handle_link)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )