import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load biến môi trường (.env khi chạy local)
load_dotenv()
# local MongoDB connection string
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGO_DB_NAME", "admin")  # mặc định kết nối vào "admin"

# atlas MongoDB connection string
# --- Mongo Atlas ---
ATLAS_URI = os.getenv("MONGO_ATLAS_URI", "")
ATLAS_DB_NAME = os.getenv("MONGO_ATLAS_DB", "websxmb")

client = None
db = None

client_atlas = None
db_atlas = None

def init_db():
    global client, db, client_atlas, db_atlas
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        print(f"✅ Đã kết nối tới MongoDB database: {DB_NAME}")
    except Exception as e:
        print("❌ Lỗi kết nối MongoDB:", e)
        raise e
    try:
        if ATLAS_URI:
            client_atlas = MongoClient(ATLAS_URI)
            db_atlas = client_atlas[ATLAS_DB_NAME]
            print(f"✅ Đã kết nối tới MongoDB Atlas database: {ATLAS_DB_NAME}")
        else:
            print("⚠️ Chưa cấu hình ATLAS_URI, bỏ qua kết nối MongoDB Atlas.")
    except Exception as e:
        print("❌ Lỗi kết nối MongoDB:", e)
        raise e
def get_db(source=None):
    global db, db_atlas

    # Nếu chỉ định rõ thì trả đúng cái đó
    if source == "local":
        if db is None:
            raise Exception("⚠️ Database local chưa được khởi tạo. Gọi init_db() trước.")
        return db
    elif source == "atlas":
        if db_atlas is None:
            raise Exception("⚠️ Database Atlas chưa được khởi tạo. Gọi init_db() trước.")
        return db_atlas

    # Nếu không chỉ định, tự động chọn Atlas nếu có, ngược lại chọn local
    # ✅ Sửa lại ở đây — dùng is not None thay vì if db
    if db_atlas is not None:
        return db_atlas
    elif db is not None:
        return db
    else:
        raise Exception("⚠️ Không có database nào được khởi tạo. Gọi init_db() trước.")
    # đang chạy local