import sys
import os
from datetime import datetime

# Thêm thư mục gốc dự án vào sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.utils.crawl import fetch_and_save_data
from models.database import init_db # 👈 thêm import này

if __name__ == "__main__":
    ngay_can_lay = "22-08-2025"
    print(f"📅 Bắt đầu lấy dữ liệu XSMB ngày {ngay_can_lay} ...")
    try:
        init_db()  # 👈 khởi tạo database trước khi gọi fetch
        fetch_and_save_data(ngay_can_lay)
        print(f"✅ Hoàn tất lưu dữ liệu ngày {ngay_can_lay} vào MongoDB.")
    except Exception as e:
        print(f"❌ Lỗi khi lấy dữ liệu: {e}")
