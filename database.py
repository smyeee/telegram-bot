import pymongo
from datetime import datetime
import pickle
import pandas as pd
import os

REQUIRED_FIELDS = [
    "_id",
    "username",
    "name",
    "phone-number",
]


class Database:
    def __init__(self) -> None:
        self.client = pymongo.MongoClient(os.environ["MONGODB_URI"])
        self.db = self.client["agriweathBot"]  # database name
        self.user_collection = self.db["newUserCollection"]
        self.bot_collection = self.db["botCollection"]
        self.dialog_collection = self.db["dialogCollection"]

    def check_if_user_exists(self, user_id: int, raise_exception: bool = False):
        if self.user_collection.count_documents({"_id": user_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} does not exist")
            else:
                return False

    def check_if_user_is_registered(self, user_id: int, required_keys: list = REQUIRED_FIELDS):
        if not self.check_if_user_exists(user_id=user_id):
            return False
        else:
            document = self.user_collection.find_one( {"_id": user_id} )
            if all(key in document for key in required_keys):
                return True
            else:
                return False

    def check_if_dialog_exists(self, user_id: int, raise_exception: bool = False):
        if self.dialog_collection.count_documents({"_id": user_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} does not exist")
            else:
                return False
    
    def add_new_user(
        self,
        user_id,
        username: str = "",
        first_seen: str = datetime.now().strftime("%Y-%m-%d %H:%M")
    ):
        user_dict = {
            "_id": user_id,
            "username": username,
            "first-seen": first_seen,
            # "phone-number": "",
            # "name": "",
            "blocked": False
        }

        if not self.check_if_user_exists(user_id=user_id):
            self.user_collection.insert_one(user_dict)


    def add_new_farm(self, user_id, farm_name: str, new_farm: dict):
        self.user_collection.update_one(
            {"_id": user_id},
            {"$set": {f"farms.{farm_name}": new_farm}}
        )

    def get_user_attribute(self, user_id: int, key: str):
        self.check_if_user_exists(user_id=user_id, raise_exception=True)
        user_dict = self.user_collection.find_one({"_id": user_id})

        if key not in user_dict:
            return None
        return user_dict[key]
    
    def set_user_attribute(self, user_id: int, key: str, value: any, array: bool = False):
        self.check_if_user_exists(user_id=user_id, raise_exception=True)
        if not array:
            self.user_collection.update_one({"_id": user_id}, {"$set": {key: value}})
        else:
            self.user_collection.update_one({"_id": user_id}, {"$push": {key: value}})
    # def log_message_to_user(self, user_id: int, message: str):
    #     self.check_if_user_exists(user_id=user_id, raise_exception=True)

    def log_new_message(
        self,
        user_id,
        username: str = "",
        message: str = "",
        function: str = "",
    ):
        current_time = datetime.now().strftime("%Y%m%d %H:%M")
        dialog_dict = {
            "_id": user_id,
            "username": username,
            "message": [f"{current_time} - {function} - {message}"],
            "function": [function]
        }

        if not self.check_if_dialog_exists(user_id=user_id):
            self.dialog_collection.insert_one(dialog_dict)
        else:
            self.dialog_collection.update_one(
                {"_id": user_id}, {
                    "$push": {"message": f"{current_time} - {function} - {message}", "function": function}})
    

    def log_sent_messages(self, users: list, function: str = "") -> None:
        current_time = datetime.now().strftime("%Y%m%d %H:%M")
        usernames = [self.user_collection.find_one({"_id": user})["username"] for user in users]
        users = [str(user) for user in users]
        log_dict = {
            "time-sent": current_time,
            "type": "sent messages",
            "function-used": function,
            "number-of-receivers": len(users),
            "receivers": dict(zip(users, usernames))
        }
        self.bot_collection.insert_one(log_dict)

    def log_member_changes(
        self,
        members: int = 0,
        time: str = "",
    ):
        bot_members_dict = {
            "num-members": [members],
            "time-stamp": [time]
        }

        if self.bot_collection.count_documents({}) == 0:
            self.bot_collection.insert_one(bot_members_dict)
        else:
            self.bot_collection.update_one({}, {"$push": {"num-members": members, "time-stamp": time}})

    def log_activity(self, user_id: int, user_activity: str, provided_value: str = ""):
        activity = {
            "user_activity": user_activity,
            "type": "activity logs",
            "value": provided_value,
            "userID": user_id,
            "username": self.user_collection.find_one({"_id": user_id})["username"],
            "timestamp": datetime.now().strftime("%Y%m%d %H:%M")
        }
        self.bot_collection.insert_one(activity)

    def get_farms(self, user_id):
        if not self.check_if_user_is_registered(user_id=user_id):
            return []
        user = self.user_collection.find_one( {"_id": user_id} )
        # provinces = user.get("provinces")
        # cities = user.get("cities")
        # villages = user.get("villages")
        # areas = user.get("areas")
        # locations = user.get("locations")
        # equality = len(provinces) == len(cities) == len(villages) == len(areas) == len(locations)
        farms = user.get("farms")
        return farms

    def get_users_without_location(self):
        pipeline = [
            { "$addFields": { "farmsArray": { "$objectToArray": "$farms" } } },
            { "$match": { "farmsArray.v.location.latitude": None, "farmsArray.v.location.longitude": None } },
            { "$project": { "_id": 1 } }
        ]
        cursor = self.user_collection.aggregate(pipeline) # users who have atleast one farm with no location
        users = [user["_id"] for user in cursor]
        return users

    def get_users_without_phone(self):
        pipeline = [
            { "$match": {"$or": [ {"phone-number": None}, {"phone-number": ""} ] } },
            { "$project": { "_id": 1 } }
        ]
        cursor = self.user_collection.aggregate(pipeline) # users with no phone number
        users = [user["_id"] for user in cursor]
        return users

    def number_of_blocks(self):
        blocked_users = self.user_collection.count_documents({"blocked": True})
        return blocked_users
    
    def populate_user_collection(
            self,
            user_id,
            username: str = "",
            product: str = "",
            province: str = "",
            city: str = "",
            village: str = "",
            area = 0,
            phone_number: str = "",
            name: str = "",
            location: dict = {},
            first_seen: str = datetime.now().strftime("%Y-%m-%d %H:%M")
        ):
            user_dict = {
                "_id": user_id,
                "username": username,
                "products": [product],
                "provinces": [province],
                "cities": [city],
                "villages": [village],
                "areas": [area],
                "phone-number": phone_number,
                "name": name,
                "locations": [location],
                "first-seen": first_seen
                # "first-seen": datetime.now().strftime("%Y-%m-%d %H:%m:%s"),
            }

            if not self.check_if_user_exists(user_id=user_id):
                self.user_collection.insert_one(user_dict)
                print(f"added {user_id} to userCollection")
    def populate_mongodb_from_pickle(self):
        with open("bot_data.pickle", "rb") as f:
            user_data = pickle.load(f)["user_data"]
        for key in user_data:
            username = user_data[key].get("username", None)
            product = user_data[key].get("produce", "")
            province = user_data[key].get("province", "")
            city = user_data[key].get("city", "")
            village = user_data[key].get("village", "")
            area = user_data[key].get("area", 0)
            phone_number = user_data[key].get("phone", "")
            name = user_data[key].get("name", "")
            location = user_data[key].get("location", {})
            first_seen = user_data[key].get("join-date")
            self.populate_user_collection(key, username, product, province, city, village, area, phone_number, name, location, first_seen)


    def to_excel(self, output_file: str) -> None:
        user_df = pd.DataFrame(columns=['id', 'username', 'phone', 'name', 'blocked', 'farm name', 'product', 'province', 'city', 'village','area', 'latitude', 'longitude', 'location method'])
        users = self.user_collection.distinct("_id")
        i = 0
        for user_id in users:
            document = self.user_collection.find_one({"_id": user_id})
            farms = self.get_farms(user_id=user_id)
            if not farms:
                user_df.loc[i] = pd.Series({
                'id': user_id,
                'username': document.get('username'),
                'phone': document.get('phone-number'),
                'name': document.get('name'),
                'blocked': document.get('blocked'),
            })
            elif len(farms) == 1:
                farm_name = list(farms.keys())[0]
                user_df.loc[i] = pd.Series({
                    'id': user_id,
                    'username': document.get('username'),
                    'phone': document.get('phone-number'),
                    'name': document.get('name'),
                    'blocked': document.get('blocked'),
                    'farm name': farm_name,
                    'area': farms[farm_name].get('areas'),
                    'product': farms[farm_name].get('products'),
                    'province': farms[farm_name].get('provinces'),
                    'city': farms[farm_name].get('cities'),
                    'village': farms[farm_name].get('villages'),
                    'latitude': farms[farm_name]['location'].get('latitude'),
                    'longitude': farms[farm_name]['location'].get('longitude'),
                    'location method': farms[farm_name].get('location-method'),
                })
                i += 1
            elif len(farms) > 1:
                for key in farms:
                    user_df.loc[i] = pd.Series({
                        'id': user_id,
                        'username': document.get('username'),
                        'phone': document.get('phone-number'),
                        'name': document.get('name'),
                        'blocked': document.get('blocked'),
                        'farm name': key,
                        'area': farms[key].get('area'),
                        'product': farms[key].get('product'),
                        'province': farms[key].get('province'),
                        'city': farms[key].get('city'),
                        'village': farms[key].get('village'),
                        'latitude': farms[key]['location'].get('latitude'),
                        'longitude': farms[key]['location'].get('longitude'),
                        'location method': farms[key].get('location-method'),
                    })
                    i += 1
        user_df.to_excel(output_file)
