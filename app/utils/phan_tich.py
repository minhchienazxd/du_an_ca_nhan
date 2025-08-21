from app.utils.crawl import get_all_results
from collections import Counter, defaultdict
from datetime import datetime, timedelta

def thong_ke_cham_trong_ngay_moi_nhat(collection):
    # Lấy kết quả ngày mới nhất
    latest_doc = sorted(
        list(collection.find()),
        key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"),
        reverse=True
    )[0]
    if not latest_doc:
        return {}

    ketqua = latest_doc.get("ketqua", {})
    tat_ca_so = []

    # Duyệt toàn bộ các giải
    for giai, value in ketqua.items():
        if isinstance(value, list):
            tat_ca_so.extend(value)
        elif isinstance(value, str):
            tat_ca_so.append(value)

    # Trích các chạm từ tất cả các số
    tat_ca_cham = []
    for so in tat_ca_so:
        for digit in so:
            if digit.isdigit():
                tat_ca_cham.append(int(digit))

    # Đếm số lần xuất hiện của từng chạm (0–9)
    dem_cham = Counter(tat_ca_cham)

    # Đảm bảo đủ 0–9, nếu thiếu gán 0
    full_cham = {i: dem_cham.get(i, 0) for i in range(10)}

    return {
        "ngay": latest_doc["date"],
        "cham": full_cham
    }

def thong_ke_tong_lo(collection):
    today = datetime.today()
    start_date = today - timedelta(days=7)
    start_str = start_date.strftime("%d-%m-%Y")

    data = list(collection.find())
    data = [d for d in data if datetime.strptime(d["date"], "%d-%m-%Y") >= datetime.strptime(start_str, "%d-%m-%Y")]
    data.sort(key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"), reverse=True)

    ket_qua_theo_ngay = {}

    for record in data:
        ngay = record["date"]
        kq = record["ketqua"]

        cac_so = []
        for giai in kq.values():
            if isinstance(giai, list):
                cac_so.extend(giai)
            else:
                cac_so.append(giai)

        lo_2_so = [s[-2:] for s in cac_so if len(s) >= 2 and s.isdigit()]

        tong_counter = {}
        for lo in lo_2_so:
            try:
                tong = (int(lo[0]) + int(lo[1])) % 10
                tong_counter[tong] = tong_counter.get(tong, 0) + 1
            except Exception as e:
                print(f"Lỗi xử lý số {lo}: {e}")

        ket_qua_theo_ngay[ngay] = tong_counter

    return ket_qua_theo_ngay


def thong_ke_lo_roi(collection, so_ngay=7, max_khoang_cach=3):
    data = list(collection.find())
    data.sort(key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"), reverse=True)
    data = data[:so_ngay]
    data.reverse()


    lo_map = defaultdict(list)
    db_map = defaultdict(list)
    all_days = []

    for doc in data:
        ngay = doc["date"]
        all_days.append(ngay)
        ketqua = doc["ketqua"]

        lo_thuong = []
        lo_db = []

        for giai, values in ketqua.items():
            if not isinstance(values, list):
                values = [values]
            for v in values:
                cap_so = v[-2:]
                if giai == "ĐB":
                    lo_db.append(cap_so)
                else:
                    lo_thuong.append(cap_so)

        for cap in set(lo_thuong):
            lo_map[cap].append(ngay)
        for cap in set(lo_db):
            db_map[cap].append(ngay)

    def tim_lo_roi(map_data):
        lo_roi = {}
        for cap, ngay_list in map_data.items():
            dates = sorted([datetime.strptime(d, "%d-%m-%Y") for d in ngay_list])
            if len(dates) < 2:
                continue

            bat_dau = dates[0]
            truoc_do = dates[0]
            count = 1

            for i in range(1, len(dates)):
                chenh_lech = (dates[i] - truoc_do).days
                if 1 <= chenh_lech <= max_khoang_cach:
                    truoc_do = dates[i]
                    count += 1
                else:
                    if count >= 2:
                        lo_roi.setdefault(cap, []).append((
                            bat_dau.strftime("%d-%m-%Y"),
                            truoc_do.strftime("%d-%m-%Y")
                        ))
                    bat_dau = truoc_do = dates[i]
                    count = 1

            if count >= 2:
                lo_roi.setdefault(cap, []).append((
                    bat_dau.strftime("%d-%m-%Y"),
                    truoc_do.strftime("%d-%m-%Y")
                ))

        return lo_roi

    return {
        "lo_thuong": tim_lo_roi(lo_map),
        "lo_db": tim_lo_roi(db_map),
        "ngay_labels": all_days
    }

from collections import defaultdict
from datetime import datetime

def phan_tich_cau_ngang(collection, so_ngay=7):
    def tach_cap_ngang(chuoi):
        return [(chuoi[i:i+2], f"vị trí {i}-{i+1}") for i in range(len(chuoi) - 1)]

    def get_last_days_data():
        all_data = list(collection.find())
        all_data.sort(key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"))
        return all_data[-so_ngay:]

    data = get_last_days_data()
    cau_ngang_result = defaultdict(list)
    ngay_cuoi = data[-1]["date"]

    for i in range(len(data) - 1):  # duyệt từ ngày 0 đến ngày -2
        ngay_truoc = data[i]
        ngay_sau = data[i + 1]
        date1 = ngay_truoc["date"]
        date2 = ngay_sau["date"]

        cap_ngay_truoc = defaultdict(list)

        # Lấy tất cả cặp số liên tiếp từ ngày trước + vị trí
        for giai, val in ngay_truoc["ketqua"].items():
            values = val if isinstance(val, list) else [val]
            for idx, v in enumerate(values):
                cap_list = tach_cap_ngang(v)
                for cap, pos in cap_list:
                    cap_ngay_truoc[cap].append((giai, f"lần {idx+1}", pos))

        # Lấy 2 số cuối của từng giải ngày sau
        hai_so_cuoi_ngay_sau = set()
        for giai, val in ngay_sau["ketqua"].items():
            values = val if isinstance(val, list) else [val]
            for v in values:
                hai_so_cuoi_ngay_sau.add(v[-2:])

        # So sánh
        for cap, chi_tiet in cap_ngay_truoc.items():
            if cap in hai_so_cuoi_ngay_sau:
                cau_ngang_result[cap].append({
                    "ngay1": date1,
                    "vitri_ngay1": chi_tiet,
                    "ngay2": date2,
                    "xuat_hien_o_ngay2": cap
                })

    # Chỉ giữ lại các cầu mà ngày cuối cùng xuất hiện là ngày_cuoi
    loc_ket_qua = {
        cap: ds for cap, ds in cau_ngang_result.items()
        if any(item["ngay2"] == ngay_cuoi for item in ds)
    }

    return loc_ket_qua


def cau_cheo(data):
    counter = Counter()
    for i in range(2, len(data)):
        truoc = data[i - 2]["data"]
        hom_nay = data[i]["data"]
        for so in truoc:
            if so in hom_nay:
                counter[so] += 1
    return counter.most_common(10)

def thong_ke_thu(data):
    thu_data = {i: Counter() for i in range(7)}
    for item in data:
        thu = datetime.strptime(item["ngay"], "%Y-%m-%d").weekday()
        thu_data[thu].update(item["data"])
    return {thu: thu_data[thu].most_common(5) for thu in thu_data}

def lap_deu(data, day_gap):
    gap_counter = Counter()
    history = defaultdict(list)
    for idx, item in enumerate(data):
        for so in item["data"]:
            history[so].append(idx)
    for so, days in history.items():
        for i in range(1, len(days)):
            if days[i] - days[i - 1] == day_gap:
                gap_counter[so] += 1
    return gap_counter.most_common(10)

def chuoi_lien_tiep(data):
    chuoi = {}
    for item in data:
        danh_sach = sorted(set(int(x) for x in item["data"]))
        temp = []
        for i in range(1, len(danh_sach)):
            if danh_sach[i] == danh_sach[i - 1] + 1:
                temp.append(f"{danh_sach[i - 1]:02}")
                temp.append(f"{danh_sach[i]:02}")
        if temp:
            chuoi[item["ngay"]] = sorted(set(temp))
    return chuoi
