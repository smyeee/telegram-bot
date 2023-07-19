from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
import database

db = database.Database

def stats_keyboard():
    keyboard = [
    [
        InlineKeyboardButton("تعداد اعضا", callback_data='member_count'),
        InlineKeyboardButton("تغییرات تعداد اعضا", callback_data='member_count_change'),
    ],
    [
        InlineKeyboardButton("دانلود فایل اکسل", callback_data='excel_download'),
    ],
]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def farms_list(user_id, edit: bool = True, delete: bool = False):
    num = db.get_farms(user_id=user_id)
    if edit & delete:
        raise ValueError("edit and error can't be True at the same time")
    elif edit:
        keyboard = [ [InlineKeyboardButton(f"باغ {i+1}", callback_data=f"edit_farm{i}")] for i in range(num) ]
        return InlineKeyboardMarkup(keyboard)
    elif delete:
        keyboard = [ [InlineKeyboardButton(f"باغ {i+1}", callback_data=f"delete_farm{i}")] for i in range(num) ]
        return InlineKeyboardMarkup(keyboard)

def return_keyboard():
    keyboard = ["back"]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
# Function to get the multi-choice keyboard for provinces
def get_province_keyboard():
    keyboard = [['کرمان', 'خراسان رضوی', 'خراسان جنوبی'], ['یزد', 'فارس', 'سمنان'], ['سایر']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


# Function to get the multi-choice keyboard for produce
def start_keyboard():
    keyboard = [['ثبت نام'], ['اضافه کردن باغ'],  ['حذف باغ'], ['ویرایش باغ های ثبت شده'], ['درخواست اطلاعات هواشناسی باغ ها']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, input_field_placeholder="ثبت نام در بات با /register")

def get_product_keyboard():
    keyboard = [['پسته اکبری', 'پسته اوحدی', 'پسته احمدآقایی'], ['پسته بادامی', 'پسته فندقی', 'پسته کله قوچی'], ['پسته ممتاز', 'سایر']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, input_field_placeholder="salam")
