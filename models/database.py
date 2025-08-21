import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

client = None
db = None 

def init_db():
    global client, db
    client = MongoClient(MONGO_URI)
    db = client["admin"]

def get_db():
    global db
    if db is None:
        raise Exception("Database chưa được khởi tạo. Gọi init_db() trước.")
    return db