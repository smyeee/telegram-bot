import logging
from logging.handlers import RotatingFileHandler
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationHandlerStop,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
import warnings
import random
import string
import database
from .keyboards import (
    payment_keyboard,
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
ASK_SS, HANDLE_SS = range(2)
HANDLE_COUPON = 0
PAYMENT_PLANS = {"یک ساله - 499000 تومان": "https://packpay.ir/abad",}
INITIAL_PRICE = 499000
MENU_CMDS = ['✍ sign up', '📤 دعوت از دیگران', '🖼 مشاهده کشت‌ها', '➕ اضافه کردن کشت', '🗑 حذف کشت', '✏️ ویرایش کشت‌ها', '🌦 درخواست اطلاعات هواشناسی', '/start', '/stats', '/send', '/set']
###################################################################
####################### Initialize Database #######################
db = database.Database()
ADMIN_LIST = db.get_admins()


## PAYMENT FUNCS
async def payment_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_activity(user.id, "chose payment from menu")
    user_data = context.user_data
    keyboard = [[InlineKeyboardButton("payment portal", url=PAYMENT_PLANS[key]) for key in list(PAYMENT_PLANS.keys())]]
    code = ''.join(random.choice(string.digits) for _ in range(5))
    user_data["code"] = code
    user_data["payment-message"] = await update.message.reply_text(f"""
💢 In order to buy the VIP service, you can use one of the methods bolow.

🔹one year subscription price: 499,000 toman

credit card:
6104 3389 6738 5168 
owner: Nima Ganji

2⃣ Enter the Payment gateway below and make the payment after entering the price.                                                                   

✅ If you have any discount code, register it using the /off command.

✅✅If you are not satisfied with the service at any time, the paid fee will be returned.

✅<b> After payment, register the image of your receipt along with the code {code} in the field of sending the receipt.</b>
""",
                                     reply_markup=InlineKeyboardMarkup(keyboard),
                                     parse_mode=ParseMode.HTML)
    db.log_payment(user.id, code=code)
    db.set_user_attribute(user.id, "payment-msg-id", user_data["payment-message"]["message_id"])
    db.set_user_attribute(user.id, "used-coupon", False)

# start of /off conversation
async def ask_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pay_message_id = db.get_user_attribute(user.id, "payment-msg-id")
    if not pay_message_id:
        db.log_activity(user.id, "used /off before starting payment process")
        await context.bot.send_message(chat_id=user.id, text="Please start the payment process from the bot menu in /start")
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="Please enter yolur discount code:",
                                       reply_markup=ReplyKeyboardRemove())
        db.log_activity(user.id, "started /off conversation")
        return HANDLE_COUPON

async def handle_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    coupon = update.message.text
    if not coupon:
        await context.bot.send_message(chat_id=user.id, text="Registration of discount code failed. You can try again /off")
        db.log_activity(user.id, "error - coupon message has no text")
        return ConversationHandler.END
    elif coupon in MENU_CMDS:
        db.log_activity(user.id, "error - coupon in menu_cmd list", coupon)
        await update.message.reply_text("The previous operation was cancelled. Please try again. /off", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif db.verify_coupon(coupon):
        if not db.get_user_attribute(user.id, "used-coupon"):
            db.set_user_attribute(user.id, "used-coupon", True)
            db.log_activity(user.id, "used a valid coupon", coupon)
            final_price = db.apply_coupon(coupon, INITIAL_PRICE)
            keyboard = [[InlineKeyboardButton("payment portal", url=PAYMENT_PLANS[key]) for key in list(PAYMENT_PLANS.keys())]]
            code = user_data["code"]
            db.add_coupon_to_payment_dict(user.id, code, coupon)
            db.modify_final_price_in_payment_dict(user.id, code, final_price)
            await context.bot.edit_message_text(chat_id=user.id, 
                                                message_id=user_data.get("payment-message")["message_id"],
                                                parse_mode=ParseMode.HTML,
                                                reply_markup= InlineKeyboardMarkup(keyboard),
                                                text=f"""
💢 To purchase VIP service, you can use the following two methods.

🔹one year subscription price: 499,000 toman

credit card:
6104 3389 6738 5168 
owner: Nima Ganji

2⃣ Enter the Payment gateway below and make the payment after entering the price.                                                                   

✅ If you have a discount code, register it using the /off command.

✅✅ If you are not satisfied with the service at any time, the paid fee will be returned.

✅<b> After payment, register the image of your receipt along with the code {code} in the field of sending the receipt.</b>
""")
            await context.bot.send_message(chat_id=user.id, text="The discount was applied", parse_mode=ParseMode.HTML,
                                        reply_to_message_id=db.get_user_attribute(user.id, "payment-msg-id"),
                                        reply_markup=payment_keyboard())
#             await context.bot.send_message(chat_id=user.id, text=f"""
# 💢 برای خرید سرویس VIP، می‌توانید از دو روش زیر اقدام کنید.

# 🔹 <s>مبلغ اشتراک یک ساله: 499,000 تومان</s>
# 🔹 مبلغ اشتراک یک ساله: {final_price} تومان
                                           
# 1⃣ شماره کارت:
# 6104 3389 6738 5168 
# به نام نیما گنجی

# 2⃣ وارد درگاه پرداخت زیر شده و با وارد کردن مبلغ، پرداخت را انجام دهید.                                                                   

# ✅ اگر کد تخفیف دارید با استفاده از دستور /off آن را ثبت کنید.

# ✅✅ در صورت عدم رضایت شما از سرویس در هر زمان، هزینه پرداختی باز می‌گردد.

# ✅<b> پس از پرداخت، تصویر فیش خود را همراه با کد {code} در قسمت ارسال فیش ثبت کنید.</b>

# """, parse_mode=ParseMode.HTML,
#                                         reply_to_message_id=db.get_user_attribute(user.id, "payment-msg-id"))

            return ConversationHandler.END
        else:
            await context.bot.send_message(chat_id=user.id, text="You have already used this discount code.")
            db.log_activity(user.id, "tried to use a coupon multiple times")
    else:
        await context.bot.send_message(chat_id=user.id, text="The discount code is not valid")
        return ConversationHandler.END

############ start of payment verification conversation ##################
async def ask_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg_id = db.get_user_attribute(user.id, "payment-msg-id")
    if not msg_id:
        await context.bot.send_message(chat_id=user.id, text="Please start the purchase process through the <b>Buy subscription</b> button.",
                                       parse_mode=ParseMode.HTML,
                                       reply_markup=payment_keyboard())
        return ConversationHandler.END
    db.log_activity(user.id, "chose ersal-e fish")
    await context.bot.send_message(chat_id=user.id, text="Please enter the payment code in the message.",
                                   reply_to_message_id=msg_id,
                                   reply_markup=ReplyKeyboardRemove())
    return ASK_SS

async def ask_ss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    code = update.message.text
    payments = db.get_user_attribute(user.id, "payments")
    all_codes = [payment['code'] for payment in payments]
    if not payments:
        await context.bot.send_message(chat_id=user.id, text="Please make the payment first.")
        db.log_activity(user.id, "error - tried to verify before starting payment process")
        return ConversationHandler.END
    elif not code or code in MENU_CMDS:
        db.log_activity(user.id, "error - payment code in menu_cmd list", code)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif code not in all_codes:
        await context.bot.send_message(chat_id=user.id, text="The entered code is incorrect.")
        db.log_activity(user.id, "error - payment code not valid", code)
        return ConversationHandler.END
    else:
        await context.bot.send_message(chat_id=user.id, text="Please send the picture of your payment")
        db.log_activity(user.id, "entered payment code", code)
        user_data["verification-code"] = code
        return HANDLE_SS
    
async def handle_ss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = context.user_data
    ss = update.message.photo
    text = update.message.text
    if text in MENU_CMDS:
        db.log_activity(user.id, "error - text in menu_cmd list", text)
        await update.message.reply_text("The previous operation was cancelled. Please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END
    elif not ss:
        db.log_activity(user.id, "error - no image was detected")
        await update.message.reply_text("NO image was recieved. If you want, use the send receipt button again", reply_markup=payment_keyboard())
        return ConversationHandler.END
    elif ss:
        db.log_activity(user.id, "sent an image")
        message_id = update.message.message_id
        await update.message.reply_text("The image of your receipt was recieved. Please wait for admin's confirm"
                                        ". The result of the review will be announced to you.",
                                        reply_markup=payment_keyboard())
        for admin in ADMIN_LIST:
            try:
                await context.bot.send_message(chat_id=admin, text=f"""confirm the payment request:
user: {user.id} 
username: {user.username}
phone-number: {db.get_user_attribute(user.id, "phone-number")}
code: {user_data["verification-code"]}
final price: {db.get_final_price(user.id, user_data["verification-code"])}
""" )
                await context.bot.forward_message(chat_id=admin,
                                              from_chat_id=user.id,
                                              message_id=message_id)
            except BadRequest or Forbidden:
                logger.warning(f"admin {admin} has deleted the bot")
        return ConversationHandler.END
    else:
        db.log_activity(user.id, "error - no valid input")
        await update.message.reply_text("The previous operation was cancelled. please try again.", reply_markup=db.find_start_keyboard(user.id))
        return ConversationHandler.END

async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    if user.id in ADMIN_LIST:
        if not args or len(args) != 2:
            await context.bot.send_message(chat_id=user.id, text="""
How to use:
/verify userID paymentCode
example:
/verify 103465015 12345
""")
        else:
            db.verify_payment(int(args[0]), args[1])
            await context.bot.send_message(chat_id=user.id, text="User's payment was confirmed.")
            await context.bot.send_message(chat_id=int(args[0]), text="Your payment has been successfully verified. Thank you for trusting us.")

async def create_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user.id in ADMIN_LIST:
        return ApplicationHandlerStop
    args = context.args
    if not len(args)==2:
        await context.bot.send_message(chat_id=user.id, text="""
the usage instruction:
/coupon text value(toman)
e.g the discount code "off-eslami", with the value of 50000 Toman is made like this:
/coupon off-eslami 50000
""")
    else:
        if db.save_coupon(args[0], args[1]):
            await context.bot.send_message(chat_id=user.id, text=f"{args[0]} {args[1]} was saved.")
        else:
            await context.bot.send_message(chat_id=user.id, text="The code was duplicated")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("The operation was cancelled!")
    return ConversationHandler.END


off_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("off", ask_coupon)],
        states={
            HANDLE_COUPON: [MessageHandler(filters.ALL, handle_coupon)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

verify_conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('🧾 send the payment receipt'), ask_code)],
    states={
        ASK_SS: [MessageHandler(filters.ALL, ask_ss)],
        HANDLE_SS: [MessageHandler(filters.ALL, handle_ss)]
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)     