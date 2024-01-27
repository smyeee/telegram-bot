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
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters
)
from telegram.error import BadRequest, Forbidden
import warnings

import database
from .regular_jobs import no_location_reminder
from .keyboards import (
    manage_farms_keyboard,
    get_product_keyboard,
    get_province_keyboard,
    farms_list_reply,
    edit_keyboard_reply,
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
CHOOSE_ATTR, EDIT_FARM, HANDLE_EDIT, HANDLE_EDIT_LINK = range(4)

MENU_CMDS = ['✍ sign up', '📤 invite others', '🖼 see the farms', '➕ add farm', '🗑 delete farm', '✏️ edit the farms', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()
###################################################################
# START OF EDIT CONVERSATION
async def edit_farm_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "start edit")
    user_farms = db.get_farms(user.id)
    if user_farms:
        # await context.bot.send_message(chat_id=user.id, text="یکی از باغ های خود را ویرایش کنید", reply_markup=farms_list(db, user.id, view=False, edit=True))
        await context.bot.send_message(
            chat_id=user.id,
            text="choose the farm:",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text="You have not registered any garden yet",
            reply_markup=db.find_start_keyboard(user.id),
        )
        return ConversationHandler.END

async def choose_attr_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # farm = update.callback_query.data
    farm = update.message.text

    user = update.effective_user
    user_data = context.user_data
    user_data["selected_farm"] = farm
    user_farms = list(db.get_farms(user.id).keys())
    if farm in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", farm)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if farm not in user_farms and farm != "↩️ back":
        db.log_activity(user.id, "error - chose wrong farm", farm)
        await context.bot.send_message(
            chat_id=user.id,
            text="Edit one of your farms",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    if farm == "↩️ back":
        db.log_activity(user.id, "back")
        await context.bot.send_message(
            chat_id=user.id, text="The operation was cancelled!", reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    db.log_activity(user.id, "chose farm to edit", farm)
    message_id = update.effective_message.message_id
    try:
        # await context.bot.edit_message_text(chat_id=user.id, message_id=message_id, text=f"انتخاب مولفه برای ویرایش در {farm}", reply_markup=edit_keyboard())
        await context.bot.send_message(
            chat_id=user.id,
            text=f"Choose one of the options below to edit:",
            reply_markup=edit_keyboard_reply(),
        )
        return EDIT_FARM
    except KeyError:
        logger.info(f"key {farm} doesn't exist.")
        return ConversationHandler.END

async def edit_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user = update.effective_user
    message_id = update.effective_message.message_id
    farm = user_data["selected_farm"]
    # attr = update.callback_query.data
    attr = update.message.text
    if attr == "back to the farms list":
        db.log_activity(user.id, "back")
        # await context.bot.edit_message_text(chat_id=user.id, message_id=message_id, text="یکی از باغ های خود را انتخاب کنید",
        #                                reply_markup=farms_list_reply(db, user.id))
        await context.bot.send_message(
            chat_id=user.id,
            text="Choose one of your farms",
            reply_markup=farms_list_reply(db, user.id),
        )
        return CHOOSE_ATTR
    if attr == "change the crop":
        db.log_activity(user.id, "chose edit product")
        user_data["attr"] = attr
        farm_doc = db.user_collection.find_one({"_id": user.id})["farms"][farm]
        if farm_doc["product"].startswith("Pistachio"):
            await context.bot.send_message(chat_id=user.id, text="Please choose the new garden's crop", reply_markup=get_product_keyboard())
        else:
            await context.bot.send_message(chat_id=user.id, text="Please write down the new crop")
        return HANDLE_EDIT
    elif attr == "change the province":
        db.log_activity(user.id, "chose edit province")
        user_data["attr"] = attr
        await context.bot.send_message(
            chat_id=user.id,
            text="Please choose your new province or write it down:",
            reply_markup=get_province_keyboard(),
        )
        return HANDLE_EDIT
    elif attr == "change the town":
        db.log_activity(user.id, "chose edit city")
        user_data["attr"] = attr
        await context.bot.send_message(chat_id=user.id, text="Please enter the new town", reply_markup=back_button())
        return HANDLE_EDIT
    elif attr == "change the village":
        db.log_activity(user.id, "chose edit village")
        user_data["attr"] = attr
        await context.bot.send_message(
            chat_id=user.id, text="Please enter the new village", reply_markup=back_button()
        )
        return HANDLE_EDIT
    elif attr == "change the area":
        db.log_activity(user.id, "chose edit area")
        user_data["attr"] = attr
        await context.bot.send_message(
            chat_id=user.id, text="Please enter the new area", reply_markup=back_button()
        )
        return HANDLE_EDIT
    elif attr == "change the location":
        db.log_activity(user.id, "chose edit location")
        user_data["attr"] = attr
        reply_text = """
Please enter your location using one of the methods below.

🟢 The Abad robot uses you location only for sending advises.
🟢 Unfortunately Abad can't send you advises without having your location .
🟢 Are you having trouble sending the location? Message @agriiadmin now for guidance.
    """
        keyboard = [
            [KeyboardButton("Send the link's address (google map or Neshan)")],
            [
                KeyboardButton(
                    "Send the location online (I'm currently in the garden)", request_location=True
                )
            ],
            [KeyboardButton("I choose using the map in telegram")],
            [KeyboardButton("back")]
        ]
        await context.bot.send_message(
            chat_id=user.id,
            text=reply_text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return HANDLE_EDIT
    else:
        db.log_activity(user.id, "error - chose wrong value to edit", attr)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END

async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    attr = user_data["attr"]
    farm = user_data["selected_farm"]
    user_farms = db.get_farms(user.id)
    ## handle the new value of attr
    if attr == "change the crop":
        new_product = update.message.text
        if new_product in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_city)
            await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        if new_product == "back":
            db.log_activity(user.id, "back")
            await context.bot.send_message(chat_id=user.id, text = "Choose one of the options below to edit:", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_product:
            db.log_activity(user.id, "error - edit product", new_product)
            await update.message.reply_text(
                "Please choose the new garden's crop",
                reply_markup=get_product_keyboard(),
            )
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.product", new_product)
        reply_text = f"The new crop {farm} was successfully registered."
        db.log_activity(user.id, "finish edit product")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif attr == "change the province":
        new_province = update.message.text
        if new_province in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_city)
            await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        if new_province == "back":
            await context.bot.send_message(chat_id=user.id, text = "Choose one of the below options for edit.", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if not new_province:
            db.log_activity(user.id, "error - edit province", new_province)
            await update.message.reply_text(
                "Please choose the new province",
                reply_markup=get_province_keyboard(),
            )
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.province", new_province)
        reply_text = f"The new province {farm} was successfully registered."
        db.log_activity(user.id, "finish edit province")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif attr == "change town":
        new_city = update.message.text
        if new_city == "back":
            await context.bot.send_message(chat_id=user.id, text = "Choose one of the below options to edit.", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if new_city in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_city)
            await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        if not new_city:
            db.log_activity(user.id, "error - edit city")
            await update.message.reply_text("Please enter the new town")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.city", new_city)
        reply_text = f"The new town {farm} was successfully registered."
        db.log_activity(user.id, "finish edit city")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif attr == "change the village":
        new_village = update.message.text
        if new_village == "back":
            await context.bot.send_message(chat_id=user.id, text = "Choose one of the options below to edit", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if new_village in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_village)
            await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        if not new_village:
            db.log_activity(user.id, "error - edit village")
            await update.message.reply_text("please enter the new village")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.village", new_village)
        reply_text = f"The new village {farm} was successfully registered."
        db.log_activity(user.id, "finish edit village")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif attr == "change the area":
        new_area = update.message.text
        if new_area == "back":
            await context.bot.send_message(chat_id=user.id, text = "Choose one of the options below to edit:", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if new_area in MENU_CMDS:
            db.log_activity(user.id, "error - answer in menu_cmd list", new_area)
            await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
            return ConversationHandler.END
        if not new_area:
            db.log_activity(user.id, "error - edit area")
            await update.message.reply_text("please enter the new area.")
            return HANDLE_EDIT
        db.set_user_attribute(user.id, f"farms.{farm}.area", new_area)
        reply_text = f"The new area {farm} was successfully registered."
        db.log_activity(user.id, "finish edit area")
        await context.bot.send_message(
            chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
        )
        return ConversationHandler.END
    elif attr == "change the location":
        new_location = update.message.location
        text = update.message.text
        if text == "back":
            db.log_activity(user.id, "back")
            await context.bot.send_message(chat_id=user.id, text = "Choose one of the below options to edit:", reply_markup=edit_keyboard_reply())
            return EDIT_FARM
        if text == "send the location (google map or Neshan)":
            db.log_activity(user.id, "chose to edit location with link")
            db.set_user_attribute(
                user.id, f"farms.{farm}.location-method", "Link via edit"
            )
            await update.message.reply_text("Please send your garden's location.", reply_markup=back_button())
            return HANDLE_EDIT_LINK
        if new_location:
            logger.info(f"{update.effective_user.id} chose: new_location sent successfully")
            db.set_user_attribute(
                user.id, f"farms.{farm}.location.longitude", new_location.longitude
            )
            db.set_user_attribute(
                user.id, f"farms.{farm}.location.latitude", new_location.latitude
            )
            db.set_user_attribute(
                user.id, f"farms.{farm}.location-method", "User sent location via edit"
            )
            reply_text = f"The new location {farm} was successfully registered."
            db.log_activity(user.id, "finish edit location", f"long: {new_location.longitude}, lat: {new_location.latitude}")
            await context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=db.find_start_keyboard(user.id)
            )
            return ConversationHandler.END
        if not new_location and text != "I choose using the map in telegram":
            logger.info(
                f"{update.effective_user.id} didn't send new_location successfully"
            )
            reply_text = """
Sending the new location of the garden was not successfully done.
Are you having trouble sending the location? ؟ message @agriiadmin now for guidance.
            """
            db.log_activity(user.id, "error - edit location", text)
            await context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=edit_keyboard_reply()
            )
            db.set_user_attribute(
                user.id, f"farms.{farm}.location-method", "Unsuccessful via edit"
            )
            context.job_queue.run_once(no_location_reminder, when=datetime.timedelta(hours=1),chat_id=user.id, data=user.username)    
            return EDIT_FARM
        elif text == "I choose from the app in telegram":
            db.log_activity(user.id, "chose to send location from map")
            logger.info(
                f"{update.effective_user.id} chose: az google map entekhab mikonam"
            )
            reply_text = """
Choose your new garden's location according to the guidance video.
    
👉  https://t.me/agriweath/2
            """
            await context.bot.send_message(
                chat_id=user.id, text=reply_text, reply_markup=ReplyKeyboardRemove()
            )
            return HANDLE_EDIT

async def handle_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    text = update.message.text
    farm = user_data["selected_farm"]
    if text in MENU_CMDS:
        db.log_activity(user.id, "error - answer in menu_cmd list", text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    if not text:
        db.log_activity(user.id, "error - no location link")
        await update.message.reply_text("Please send the location link of your garden.", reply_markup=back_button())
        return HANDLE_EDIT_LINK
    elif text == "back":
        db.log_activity(user.id, "back")
        reply_text = "Please send your garden's location using one of the below options."
        keyboard = [
        [KeyboardButton("send location's link (google map or Neshan)")],
        [
            KeyboardButton(
                "Send location (I'm currently in the garden)", request_location=True
            )
        ],
        [KeyboardButton("I choose using the map in telegram")],
        [KeyboardButton("back")]
        ]
        await update.message.reply_text(
            reply_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return HANDLE_EDIT
    reply_text = "Sending the location was successfully done. Please wait for admin's approval. Thanks!"
    db.set_user_attribute(user.id, f"farms.{farm}.link-status", "To be verified")
    db.log_activity(user.id, "finish edit location with link")
    await update.message.reply_text(reply_text, reply_markup=db.find_start_keyboard(user.id))
    context.job_queue.run_once(no_location_reminder, when=datetime.timedelta(hours=1),chat_id=user.id, data=user.username)    
    for admin in ADMIN_LIST:
        try:
            await context.bot.send_message(chat_id=admin, text=f"user {user.id} sent us a link for\nname:{user_data['selected_farm']}\n{text}")
        except BadRequest or Forbidden:
            logger.warning(f"admin {admin} has deleted the bot")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The operation was candelled")
    return ConversationHandler.END


edit_farm_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("✏️ edit the farms"), edit_farm_keyboard)],
        states={
            CHOOSE_ATTR: [MessageHandler(filters.ALL, choose_attr_to_edit)],
            EDIT_FARM: [MessageHandler(filters.ALL, edit_farm)],
            HANDLE_EDIT: [MessageHandler(filters.ALL, handle_edit)],
            HANDLE_EDIT_LINK: [MessageHandler(filters.ALL, handle_edit_link)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )