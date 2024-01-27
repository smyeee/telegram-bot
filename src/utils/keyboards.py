from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
import database

db = database.Database

def stats_keyboard():
    keyboard = [
    [
        InlineKeyboardButton("member count", callback_data='member_count'),
        InlineKeyboardButton("changes of member count", callback_data='member_count_change')
    ],
    [
        InlineKeyboardButton("block count", callback_data='block_count'),
        InlineKeyboardButton("member count without location", callback_data='no_location_count'),
        
    ],
    [
        # InlineKeyboardButton("دانلود فایل اکسل", callback_data='excel_download'),
        InlineKeyboardButton("member count without phone", callback_data='no_phone_count'),
    ],
    # [
    #     InlineKeyboardButton("پراکندگی لوکیشن اعضا", callback_data='html_map'),
    # ],
]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def farms_list_inline(database: db, user_id, view: bool = True, edit: bool = False):
    farms = database.get_farms(user_id=user_id)
    if not farms:
        return None
    keys_list = list(farms.keys())
    if view & edit:
        raise ValueError("edit and error can't be True at the same time")
    elif view:
        keyboard = [ [InlineKeyboardButton(key, callback_data=f"{key}")] for key in keys_list ]
        return InlineKeyboardMarkup(keyboard)
    elif edit:
        keyboard = [ [InlineKeyboardButton(key, callback_data=f"{key}")] for key in keys_list ]
        return InlineKeyboardMarkup(keyboard)
    
def farms_list_reply(database: db, user_id, pesteh_kar: bool = None):
    farms = database.get_farms(user_id=user_id)
    if not farms:
        return None
    keys_list = list(farms.keys())
    if pesteh_kar:
        keyboard = [ [key] for key in keys_list if farms[key].get("product", "").startswith("پسته")]
    else:
        keyboard = [ [key] for key in keys_list ]
    keyboard.append(["↩️ back"])
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
def edit_keyboard_inline():
    keyboard = [
    [
        InlineKeyboardButton("change the crop", callback_data='product'),
        InlineKeyboardButton("change the province", callback_data='province')
    ],
    [
        InlineKeyboardButton("change the town", callback_data='city'),
        InlineKeyboardButton("change the village", callback_data='village')
    ],
    [
        InlineKeyboardButton("change the area", callback_data='area'),
        InlineKeyboardButton("change the location", callback_data='location'),
    ],
    [
        InlineKeyboardButton("back to the garden's list", callback_data='back'),
    ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def edit_keyboard_reply():
    keyboard = [
    [
        "change the crop",
        "change the province",
    ],
    [
        "change the town",
        "change the village",
    ],
    [
        "change the area",
        "change the location",
    ],
    [
        "back to the farm's list",
    ]
    ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def land_type_keyboard():
    keyboard = [["garden", "farm"], ["herb", "green house"], ['back']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)


def return_keyboard():
    keyboard = ["back"]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
# Function to get the multi-choice keyboard for provinces
def get_province_keyboard():
    keyboard = [['Kerman', 'Khorasan razavi', 'Khorasan jonoobi'], ['Yazd', 'Fars', 'Semnan'], ['Markazi', 'Tehram', 'Esfehan'], ['Ghom', 'Sistan va baloochestan', 'Ghazvin'], ['back']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

# 🌳🧾💶💰✅

# Function to get the multi-choice keyboard for produce
# def start_keyboard():
#     keyboard = [['📤 دعوت از دیگران'], ,  ['🗑 حذف باغ ها', '✏️ ویرایش باغ ها'], ['🌦 درخواست اطلاعات هواشناسی']]
#     return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


def start_keyboard_not_registered():
    keyboard = [ ["✍ sign up"] ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


def start_keyboard_no_farms():
    keyboard = [ ["➕ add farm"] ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def start_keyboard_no_location():
    keyboard = [ ["✏️ edit the farms"] ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def start_keyboard_not_pesteh():
    keyboard = [ ['👨‍🌾 manage the farms'],  ['🌟 VIP service'] , ['🌦 weather forecast', '🧪 spraying conditions'],  ['📤 invite others', '📬 contact us']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def start_keyboard_pesteh_kar():
    keyboard = [ ['🌦weather forecast'], ['Pre-harvest advice', 'Post-harvest advice'], ['🧪 Spraying conditions'], ['❄️ cold demand'], ['🏘 back to home'] ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def home_keyboard_pesteh_kar():
    keyboard = [ ['👨‍🌾crops management'],  ['🌟 VIP service'] , ['📤 invite others', '📬 contact us'], ['meteorology menu']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)


def manage_farms_keyboard():
    keyboard = [['🖼 see the farms', '➕ add farm'], ['🗑 delete the farm', '✏️ edit the farms'], ['🏘 back to home']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)

def payment_keyboard():
    keyboard = [['💶 subscribe'], ['🧾 send the payment receipt'], ['🏘 back to home']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)

def request_info_keyboard():
    keyboard = [ ['🌦 Request weather information'],  ['🧪 Receive spraying advicec'], ['🏘 Back to home']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def view_advise_keyboard(farm_name: str):
    keyboard = [
        [
        InlineKeyboardButton("توصیه پس‌فردا", callback_data=f'{farm_name}\nday3_advise'),
        InlineKeyboardButton("توصیه فردا", callback_data=f'{farm_name}\nday2_advise'),
        InlineKeyboardButton("توصیه امروز", callback_data=f'{farm_name}\ntoday_advise'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def view_sp_advise_keyboard(farm_name: str):
    keyboard = [
        [
        InlineKeyboardButton("توصیه پس‌فردا", callback_data=f'{farm_name}\nday3_sp_advise'),
        InlineKeyboardButton("توصیه فردا", callback_data=f'{farm_name}\nday2_sp_advise'),
        InlineKeyboardButton("توصیه امروز", callback_data=f'{farm_name}\ntoday_sp_advise'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def register_keyboard():
    keyboard = [['✍ sign up']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def get_product_keyboard():
    keyboard = [['Akbari pistachio', 'Ohedi pistachio', 'Ahmad aghayi pistachio'], ['Badami pistachio', 'fandoghi pistachio', 'Kalle ghoochi pistachio'], ['first class pistachio', 'back']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def conf_del_keyboard():
    keyboard = [['yes'], ['no'], ['back']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def automn_month():
    keyboard = [['Aban'], ['Azar'], ['↩️ back']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def automn_week():
    keyboard = [['the second week', 'the first week'], ['the forth week', ' the third week'], ['↩️ back']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def choose_role():
    keyboard = [['specify the id'], ['all the users'], ['They did not hit the registration button'], ['pistachio farmers'], ['include the location'], ['without the location'], ['without phone number'], ['back']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True ,one_time_keyboard=True)

def back_button():
    keyboard = [['back']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True ,one_time_keyboard=True)