import requests
from datetime import datetime, timedelta, date
from models.database import get_db, init_db
from bs4 import BeautifulSoup
from cloudscraper import create_scraper
from collections import Counter, defaultdict

# Hàm định dạng ngày để LƯU vào database (dạng 31-7-2025)
def format_date_for_db(d: date) -> str:
    return f"{d.day}-{d.month}-{d.year}"

# Hàm định dạng ngày để HIỂN THỊ (dạng 31-07-2025)
def format_date_for_display(date_str: str) -> str:
    d = datetime.strptime(date_str, "%d-%m-%Y")
    return d.strftime("%d-%m-%Y")  # dùng lại nhưng đảm bảo luôn có 0

# Lấy dữ liệu từ web và lưu vào MongoDB
def fetch_and_save_data(selected_date: date = None):
    if isinstance(selected_date, str):
        selected_date = datetime.strptime(selected_date, "%d-%m-%Y").date()
    if not selected_date:
        selected_date = date.today()

    url = f"https://xoso.com.vn/xsmb-{selected_date.strftime('%d-%m-%Y')}.html"
    scraper = create_scraper()
    response = scraper.get(url)

    if response.status_code != 200:
        print("❌ Lỗi khi lấy dữ liệu!")
        return

    soup = BeautifulSoup(response.text, 'lxml')

    def get_prize(name):
        return [p.text.strip() for p in soup.find_all(class_=name)]

    result = {
        "date": format_date_for_db(selected_date),  # lưu dạng 31-7-2025
        "countNumbers": 0,
        "ketqua": {
            "ĐB": get_prize("special-prize"),
            "G1": get_prize("prize1"),
            "G2": get_prize("prize2"),
            "G3": get_prize("prize3"),
            "G4": get_prize("prize4"),
            "G5": get_prize("prize5"),
            "G6": get_prize("prize6"),
            "G7": get_prize("prize7"),
        }
    }

    result["countNumbers"] = sum(len(v) for v in result["ketqua"].values())

    db = get_db()
    db.kq_xs.update_one(
        {"date": result["date"]},
        {"$set": result},
        upsert=True
    )
    print(f"✅ Đã lưu/cập nhật kết quả XSMB ngày {format_date_for_display(result['date'])} vào MongoDB.")

# Lấy kết quả hôm nay từ DB
def get_today_result():
    today = date.today()
    today_str = format_date_for_db(today)
    db = get_db()
    return db.kq_xs.find_one({"date": today_str})

# Lấy kết quả theo ngày cụ thể
def get_result_by_date(date_str):
    db = get_db()
    return db.kq_xs.find_one({"date": date_str})

# Lấy tất cả kết quả (mới nhất lên đầu)
def get_all_results():
    db = get_db()
    return list(db.kq_xs.find().sort("date", -1))

# Thống kê đầu - đuôi từ kết quả
def thong_ke_dau_duoi(ketqua):
    thong_ke = {str(i): [] for i in range(10)}  # Đầu 0–9

    for giai, danh_sach in ketqua.items():
        for so in danh_sach:
            if len(so) >= 2:
                hai_so_cuoi = so[-2:]
                dau, duoi = hai_so_cuoi[0], hai_so_cuoi[1]
                if dau.isdigit() and duoi.isdigit():
                    thong_ke[dau].append(duoi)

    return thong_ke

# Lấy 5 ngày gần nhất (trừ 1 ngày nếu cần) và thống kê
def get_past_5_results_with_stats(get_result_by_date_func, thong_ke_func, exclude_date=None):
    today = datetime.today()
    results = []

    exclude = datetime.strptime(exclude_date, "%d-%m-%Y") if exclude_date else None
    i = 1
    while len(results) < 5:
        day = today - timedelta(days=i)
        if exclude and day.date() == exclude.date():
            i += 1
            continue

        day_str = format_date_for_db(day.date())
        result = get_result_by_date_func(day_str)
        if result:
            thong_ke = thong_ke_func(result["ketqua"])
            results.append({
                "date": format_date_for_display(day_str),
                "ketqua": result["ketqua"],
                "thong_ke": thong_ke
            })
        i += 1
    return results

# Test chạy trực tiếp file
if __name__ == "__main__":
    init_db()
    fetch_and_save_data()
