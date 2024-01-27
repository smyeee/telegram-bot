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
    manage_farms_keyboard,
    get_product_keyboard,
    get_province_keyboard,
    back_button,
    land_type_keyboard
)
from .logger import logger
from .sms_funcs import sms_incomplete_farm
# Constants for ConversationHandler states
(
    ASK_TYPE,
    ASK_PRODUCT,
    HANDLE_PRODUCT,
    ASK_PROVINCE,
    ASK_CITY,
    ASK_VILLAGE,
    ASK_AREA,
    ASK_LOCATION,
    HANDLE_LOCATION,
    HANDLE_LINK
) = range(10)

MENU_CMDS = ['✍ sign up', '📤 invite others', '🖼 visit the farms', '➕ add farm', '🗑 delete farm', '✏ edit farms', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']

MESSAGES = {
    ""
}
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()

# START OF ADD_FARM CONVERSATION
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start add farm")
    if not db.check_if_user_is_registered(user_id=user.id):
        db.log_activity(user.id, "error - add farm", "not registered yet")
        await update.message.reply_text(
            "Please sign up using start/ before adding any garden",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END
    reply_text = """
Please enter a name to recognize this farm:
e.g. Pistachio garden
"""
    await update.message.reply_text(reply_text, reply_markup=back_button())
    job_data = {"timestamp": datetime.datetime.now().strftime("%Y%m%d %H%M")}
    if datetime.time(2, 30).strftime("%H%M") <= datetime.datetime.now().strftime("%H%M") < datetime.time(17, 30).strftime("%H%M"):
        context.job_queue.run_once(sms_incomplete_farm, when=datetime.timedelta(hours=1), chat_id=user.id, data=job_data)
    else:
        context.job_queue.run_once(sms_incomplete_farm, when=datetime.time(4, 30), chat_id=user.id, data=job_data)
    return ASK_TYPE


async def ask_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and handles <<name>>"""
    user = update.effective_user
    user_data = context.user_data
    message_text = update.message.text
    if message_text == "back":
        db.log_activity(user.id, "back")
        await update.message.reply_text("The operation was cancelled", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif "." in message_text:
        db.log_activity(user.id, "error - chose name with .", f"{message_text}")
        reply_text = (
                "The garden's name should not include <b>'.'</b> . Please choose anothere name"
            )
        await update.message.reply_text(reply_text, reply_markup=back_button(), parse_mode=ParseMode.HTML)
        return ASK_TYPE
    elif not message_text:
        db.log_activity(user.id, "error - no name received")
        reply_text = """
Please enter a name to recognize this farm:
e.g. Pistachio garden
"""
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_TYPE
    elif db.user_collection.find_one({"_id": user.id}).get("farms"):
        used_farm_names = db.user_collection.find_one({"_id": user.id})["farms"].keys()
        if message_text in used_farm_names:
            db.log_activity(user.id, "error - chose same name", f"{message_text}")
            reply_text = (
                "You have used this name before. Please choose another name."
            )
            await update.message.reply_text(reply_text, reply_markup=back_button())
            return ASK_TYPE
    farm_name = message_text.strip()
    user_data["farm_name"] = farm_name
    db.log_activity(user.id, "chose name", farm_name)
    new_farm_dict = {
        "type": None,
        "product": None,
        "province": None,
        "city": None,
        "village": None,
        "area": None,
        "location": {"latitude": None, "longitude": None},
        "location-method": None
    }
    db.add_new_farm(user_id=user.id, farm_name=farm_name, new_farm=new_farm_dict)
    reply_text = """
Please choose your farm type.
If your farm's type is not between the options write it down.
"""
    # await update.message.reply_text(reply_text, reply_markup=back_button())
    await update.message.reply_text(reply_text, reply_markup=land_type_keyboard())
    return ASK_PRODUCT


async def ask_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives and handles <<land_type>>"""
    user = update.effective_user
    user_data = context.user_data
    message_text = update.message.text
    # logger.info(update.message.text)
    if message_text == "back":
        db.log_activity(user.id, "back")
        reply_text = """
Please enter a name to recognize this farm:
e.g. Pistachio garden
"""
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return ASK_TYPE
    elif message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("The previous operation was ccancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif "." in message_text:
        db.log_activity(user.id, "error - chose land type with .", f"{update.message.text}")
        reply_text = (
                "The farm's type can not include any <b>'.'</b> Please enter it again."
            )
        await update.message.reply_text(reply_text, reply_markup=land_type_keyboard(), parse_mode=ParseMode.HTML)
        return ASK_PRODUCT
    elif not message_text:
        db.log_activity(user.id, "error - no name received")
        reply_text = """
Please choose your farm's type. 
If your farm's type is not betweent the options, write it down.
"""
        await update.message.reply_text(reply_text, reply_markup=land_type_keyboard())
        return ASK_PRODUCT


    farm_name = user_data["farm_name"]
    land_type = message_text.strip()
    user_data["land_type"] = land_type
    db.log_activity(user.id, "chose land type", land_type)
    db.set_user_attribute(user.id, f"farms.{farm_name}.type", land_type)
    if land_type == "garden":
        await update.message.reply_text(
            "Please choose garden's crop. \n Incase you don't have any Pistachio garden, enter the crop of your garden .",
            reply_markup=ReplyKeyboardMarkup([["Pistachio", "back"]], resize_keyboard=True, one_time_keyboard=True))
        return HANDLE_PRODUCT
    else:
        await update.message.reply_text("What crop do you cultivate?", reply_markup=back_button()
        )
        return ASK_PROVINCE


async def handle_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the farm name"""
    user = update.effective_user
    user_data = context.user_data
    land_type = user_data["land_type"]
    message_text = update.message.text
    # logger.info(update.message.text)
    if message_text == "back":
        db.log_activity(user.id, "back")
        reply_text = """
Please choose your farm's type. 
If your farm's type is not betweent the options, write it down.
"""
        await update.message.reply_text(reply_text, reply_markup=land_type_keyboard())
        return ASK_PRODUCT
    elif message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif "." in message_text:
        db.log_activity(user.id, "error - chose product with .", f"{message_text}")
        reply_text = (
                "The crop's name should not include <b>'.'.</b> Please write down the crop's name without <b>'.'</b>. "
            )
        await update.message.reply_text(reply_text, reply_markup=back_button(), parse_mode=ParseMode.HTML)
        return HANDLE_PRODUCT
    elif not message_text:
        db.log_activity(user.id, "error - no product received")
        if land_type == "garden":
            keyboard = ReplyKeyboardMarkup([["Pistachio", "back"]], resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text(
                "Please choose the garden's crop. \n Incase you do not have any Pistachio garden, write down your garden's crop.", reply_markup=keyboard
            )
            return HANDLE_PRODUCT
        else:
            await update.message.reply_text("What crop do you cultivate?", reply_markup=back_button()
            )
            return HANDLE_PRODUCT
    user_data["farm_product"] = message_text
    if land_type == "garden" and message_text == "Pistachio":
        db.log_activity(user.id, "chose product", "Pistachio")
        await update.message.reply_text(
            "Please choose the pistachio type of your garden ", reply_markup=get_product_keyboard()
        )
        return ASK_PROVINCE
    else:
        await update.message.reply_text(
            "Please enter your crop one more time.")
        return ASK_PROVINCE

async def ask_province(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ 
    If land_type==باغ this function receives output of handle_product
    Otherwise will receive output of ask_product
    """
    user = update.effective_user
    user_data = context.user_data
    message_text = update.message.text
    land_type = user_data["land_type"]

    if message_text == "back":
        db.log_activity(user.id, "back")
        if land_type != "باغ":
            reply_text = """
Please choose your farm's type.
If your farm's type is not between the options, write it down.
"""
            await update.message.reply_text(reply_text, reply_markup=land_type_keyboard())
            return ASK_PRODUCT
        else:
            await update.message.reply_text(
            "Please choose the garden's crop \n Incase you don't have any Pistachio garden, write down your garden's crop.",
            reply_markup=ReplyKeyboardMarkup([["Pistachio", "back"]], resize_keyboard=True, one_time_keyboard=True))
            return HANDLE_PRODUCT
    # Get the answer to the province question
    elif message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not message_text or "." in message_text:
        db.log_activity(user.id, "error - chose wrong product", f"{update.message.text}")
        await update.message.reply_text(
            "Please restart the process", reply_markup=get_product_keyboard()
        )
        return ConversationHandler.END
    product = message_text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.product", product)
    db.log_activity(user.id, "chose product", f"{product}")
    await update.message.reply_text(
        "Please choose your province. \If your province is not between the options write it down.", reply_markup=get_province_keyboard()
    )
    return ASK_CITY

async def ask_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    message_text = update.message.text
    land_type = user_data["land_type"]

    if message_text == "back":
        db.log_activity(user.id, "back")
        if land_type != "باغ":
            await update.message.reply_text("What crop do you cultivate?", reply_markup=back_button()
        )
            return ASK_PROVINCE
        else:
            await update.message.reply_text(
            "Please choose your garden's crop. \n If you don't have Pistachio garden write down your garden's crop.",
            reply_markup=ReplyKeyboardMarkup([["Pistachio", "back"]], resize_keyboard=True, one_time_keyboard=True))
            return HANDLE_PRODUCT

        # await update.message.reply_text(
        #     "لطفا محصول باغ را انتخاب کنید", reply_markup=get_product_keyboard()
        # )
        # return ASK_PROVINCE
    # Get the answer to the province question
    elif message_text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", message_text)
        await update.message.reply_text("The previous operation was cancelled. Please try again..", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not message_text:
        db.log_activity(user.id, "error - chose wrong province", f"{update.message.text}")
        await update.message.reply_text(
            "Please choose your farm's province or write it down.",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    province = message_text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.province", province)
    db.log_activity(user.id, "chose province", f"{province}")
    await update.message.reply_text(
        "Please enter the farm's town:", reply_markup=back_button()
    )
    return ASK_VILLAGE

async def ask_village(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "back":
        db.log_activity(user.id, "back")
        await update.message.reply_text(
            "Please enter your farm's province:",
            reply_markup=get_province_keyboard(),
        )
        return ASK_CITY
    # Get the answer to the province question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - city")
        await update.message.reply_text(
            "Please enter the farm's town:", reply_markup=back_button()
        )
        return ASK_VILLAGE
    city = update.message.text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.city", city)
    db.log_activity(user.id, "entered city", f"{city}")
    await update.message.reply_text(
        "Please enter the farm's village and its address:", reply_markup=back_button()
    )
    return ASK_AREA

async def ask_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "back":
        db.log_activity(user.id, "back")
        await update.message.reply_text("Please enter farm's town:", reply_markup=back_button())
        return ASK_VILLAGE
    # Get the answer to the village question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - village")
        await update.message.reply_text(
            "Please enter the farm's village and its address:", reply_markup=back_button()
        )
        return ASK_AREA
    village = update.message.text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.village", village)
    db.log_activity(user.id, "entered village", f"{village}")
    await update.message.reply_text("Please enter your farm's area in hectares:", reply_markup=back_button())
    return ASK_LOCATION

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "back":
        db.log_activity(user.id, "back")
        await update.message.reply_text("Please enter the farm's village and its address", reply_markup=back_button())
        return ASK_AREA
    # Get the answer to the phone number question
    if update.message.text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not update.message.text:
        db.log_activity(user.id, "error - area")
        await update.message.reply_text("Please enter your farm,s area in hectares:", reply_markup=back_button())
        return ASK_LOCATION
    area = update.message.text.strip()
    farm_name = user_data["farm_name"]
    db.set_user_attribute(user.id, f"farms.{farm_name}.area", area)
    db.log_activity(user.id, "entered area", f"{area}")
    reply_text = """
Please enter your garden's location using one of the methods below.

🟢 The Abad's robot uses your location only for sending advices.
🟢 Unfortunately Abad can't send you any advice without having your location.
🟢 Are you having any trouble sending the locaiton? Message @agriiadmin now for guidance.
    """
    keyboard = [
        [KeyboardButton("Sending the link address (google map or Neshan)")],
        [
            KeyboardButton(
                "Send the location, online (I'm in the garden right now)", request_location=True
            )
        ],
        [KeyboardButton("I choose using th e map in telegram.")],
        [KeyboardButton("back")]
    ]
    await update.message.reply_text(
        reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HANDLE_LOCATION

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    if update.message.text == "back":
        db.log_activity(user.id, "back")
        await update.message.reply_text("Please enter your farm's area in hectares:", reply_markup=back_button())
        return ASK_LOCATION
    if update.message.text == "Sending the link address (google map or Neshan)":
        db.log_activity(user.id, "chose location link")
        reply_text = """
 Please send your location's link, according to the guidance video.
 
👉 https://t.me/agriweath/59 

If you need any help, message @agriiadmin now.
"""
        await update.message.reply_text(reply_text, reply_markup=back_button())
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
your garden with the name{farm_name}> was successfully registered,
The climate related advices will be sent to you from the incoming days.
To edit or visit the garden's information use the related options in /start.
"""
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not location and text != "I choose using the map in telegram":
        db.log_activity(user.id, "error - location", text)
        logger.info(f"{update.effective_user.id} didn't send location successfully")
        reply_text = "Sendig the location was not successfully done. You can register the location through 'edit the garden'."

        db.set_user_attribute(user.id, f"farms.{farm_name}.location-method", "Unsuccessful")
        db.log_activity(user.id, "finish add farm - no location", farm_name)

        context.job_queue.run_once(no_location_reminder, when=datetime.timedelta(hours=1),chat_id=user.id, data=user.username)
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif text == "I choose using the map in telegram":
        db.log_activity(user.id, "chose to send location from map")
        logger.info(f"{update.effective_user.id} chose: az google map entekhab mikonam")
        reply_text = """
        Choose your location according to the guidance video.
        
        👉  https://t.me/agriweath/2
        """
        await update.message.reply_text(reply_text, reply_markup=back_button())
        return HANDLE_LOCATION

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    text = update.message.text
    farm_name = user_data["farm_name"]
    if text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", update.message.text)
        await update.message.reply_text("The operation was cancelled. Please try again", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not text:
        db.log_activity(user.id, "error - no location link")
        await update.message.reply_text("Please send the location link of your garden", reply_markup=back_button())
        return HANDLE_LINK
    elif text == "back":
        db.log_activity(user.id, "back")
        reply_text = "Please send your garden's location using one of the methods below."
        keyboard = [
        [KeyboardButton("send the link address (google map or Neshan)")],
        [
            KeyboardButton(
                "send the location online (I'm currently in the garden)", request_location=True
            )
        ],
        [KeyboardButton("I choose using the map in telegram")],
        [KeyboardButton("back")]
        ]
        await update.message.reply_text(
            reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return HANDLE_LOCATION
    else:
        db.log_activity(user.id, "sent location link", text)
        reply_text = "Sending the link address was successfully done. Please wait utill the admin surveys.\n Thanks for your patience."
        db.set_user_attribute(user.id, f"farms.{farm_name}.location-method", "Link")
        db.set_user_attribute(user.id, f"farms.{farm_name}.link-status", "To be verified")
        db.log_activity(user.id, "finish add farm with location link", farm_name)
        context.job_queue.run_once(no_location_reminder, when=datetime.timedelta(hours=1), chat_id=user.id, data=user.username)
        await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
        for admin in ADMIN_LIST:
            try:
                await context.bot.send_message(chat_id=admin, text=f"user {user.id} sent us a link for\nname:{farm_name}\n{text}")
            except BadRequest or Forbidden:
                logger.warning(f"admin {admin} has deleted the bot")
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The operation was cancelled.")
    return ConversationHandler.END


add_farm_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('➕ add farm'), add)],
        states={
            ASK_TYPE: [MessageHandler(filters.TEXT, ask_type)],
            ASK_PRODUCT: [MessageHandler(filters.TEXT, ask_product)],
            HANDLE_PRODUCT: [MessageHandler(filters.TEXT, handle_product)],
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