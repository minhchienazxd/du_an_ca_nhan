import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load biến môi trường (.env khi chạy local)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGO_DB_NAME", "admin")  # mặc định kết nối vào "admin"

client = None
db = None

def init_db():
    global client, db
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        print(f"✅ Đã kết nối tới MongoDB database: {DB_NAME}")
    except Exception as e:
        print("❌ Lỗi kết nối MongoDB:", e)
        raise e

def get_db():
    global db
    if db is None:
        raise Exception("⚠️ Database chưa được khởi tạo. Hãy gọi init_db() trước.")
    return db
