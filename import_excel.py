import pandas as pd
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

client = MongoClient("mongodb+srv://nandud7967_db_user:bmQJHC59oLWxsdzd@cluster0.mqiwdmb.mongodb.net/?appName=Cluster0")
db = client["cable_db"]
customers = db["customers"]

df = pd.read_excel("LCOSTBNO.xlsx")

for _, row in df.iterrows():
    record = {
        "card_number": str(row["card_number"]).strip(),
        "stb_number": str(row["stb_number"]).strip(),
        "monthly_amount": 0
    }

    try:
        customers.insert_one(record)
        print("Inserted:", record["card_number"])

    except DuplicateKeyError:
        print("Skipped duplicate STB:", record["stb_number"])

    except Exception as e:
        print("Other error:", e)

print("Import Finished Successfully!")