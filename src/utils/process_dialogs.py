import pandas as pd
import json
from datetime import datetime

with open("dialogCollection.json", "r") as f:
    json_data = json.load(f)

data = []
for entry in json_data:
    username = entry["username"]
    _id = entry["_id"]
    messages = entry["message"]

    # Extract dates from each message and store them in a set to eliminate duplicates
    dates = set()
    for message in messages:
        date_str = message.split(" - ")[0]
        date = datetime.strptime(date_str, "%Y%m%d %H:%M")
        dates.add(date.date())

    # Create a dictionary for each entry with dates as keys and messages as values
    entry_data = {"_id": _id, "username": username}
    for date in dates:
        messages_on_date = [message for message in messages if message.startswith(date.strftime("%Y%m%d"))]
        print(messages_on_date)
        entry_data[str(date)] = messages_on_date

    data.append(entry_data) 
df = pd.DataFrame(data)
date_columns = sorted([col for col in df.columns if col not in ["_id", "username"]], key=lambda x: datetime.strptime(x, "%Y-%m-%d"))
df = df[["_id", "username"] + date_columns]
# df = df.reindex(sorted(df.columns, key=lambda x: datetime.strptime(x, "%Y-%m-%d")), axis=1)
df.to_excel("dialog_output.xlsx", index=False, engine="openpyxl")

