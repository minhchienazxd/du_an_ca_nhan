from pymongo import MongoClient

# Kết nối đến MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["admin"]  # Thay tên DB cho phù hợp

# Collection tên là "bank"
bank_collection = db["bank"]

# Danh sách tài khoản ngân hàng mẫu
sample_banks = [
    {
        "bank_name": "Vietcombank",
        "account_number": "0123456789",
        "account_name": "Nguyen Van A"
    },
    {
        "bank_name": "Techcombank",
        "account_number": "1234567890",
        "account_name": "Tran Thi B"
    },
    {
        "bank_name": "MB Bank",
        "account_number": "18092003",
        "account_name": "Lê minh chiến"
    }
]

# Chỉ thêm nếu chưa có dữ liệu nào
if bank_collection.count_documents({}) == 0:
    bank_collection.insert_many(sample_banks)
    print("✅ Đã thêm các tài khoản ngân hàng mẫu.")
else:
    print("⚠️ Dữ liệu ngân hàng đã tồn tại.")
