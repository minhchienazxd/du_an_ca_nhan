from pymongo import MongoClient
from werkzeug.security import generate_password_hash

# Thay đổi URL kết nối nếu cần
client = MongoClient("mongodb://localhost:27017/")
db = client["admin"]  # Đổi tên database cho phù hợp

# Tên collection admin
admin_collection = db["admins"]

# Kiểm tra đã có admin chưa
admin_email = "chienkim65@gmail.com"
existing_admin = admin_collection.find_one({"email": admin_email})

if not existing_admin:
    admin_user = {
        "name": "Admin",
        "email": admin_email,
        "password": generate_password_hash("admin123"),  # Băm mật khẩu
        "role": "admin"
    }
    admin_collection.insert_one(admin_user)
    print("✅ Đã tạo tài khoản admin:", admin_email)
else:
    print("⚠️ Admin đã tồn tại:", admin_email)
