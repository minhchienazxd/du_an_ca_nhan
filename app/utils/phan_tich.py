from collections import Counter, defaultdict
from datetime import datetime, timedelta

def phan_tich_cham(collection):
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

def phan_tich_tong_lo(collection):
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


def phan_tich_lo_roi(collection, so_ngay=7, max_khoang_cach=3):
    data = get_last_days(collection, so_ngay)
    data.reverse()  # đảo lại theo ngày tăng dần (từ cũ → mới)


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

def get_last_days(collection, so_ngay=7):
    # Lấy toàn bộ dữ liệu
    docs = list(collection.find({}))
    
    # Thêm field date_obj để sort
    for d in docs:
        try:
            d["date_obj"] = datetime.strptime(d["date"], "%d-%m-%Y")
        except:
            d["date_obj"] = None
    
    # Bỏ doc lỗi ngày
    docs = [d for d in docs if d["date_obj"]]

    # Sort theo ngày giảm dần (mới nhất trước)
    docs = sorted(docs, key=lambda x: x["date_obj"], reverse=True)
    
    # Trả về 7 ngày gần nhất
    return docs[:so_ngay]

def get_all_last_two_digits(ketqua_dict):
    """
    Lấy tất cả 2 số cuối từ kết quả xổ số
    """
    last_two_digits = []
    for values in ketqua_dict.values():
        if isinstance(values, list):
            for v in values:
                if len(v) >= 2:
                    last_two_digits.append(v[-2:])
        else:
            if len(values) >= 2:
                last_two_digits.append(values[-2:])
    return last_two_digits

def has_valid_ketqua(doc):
    """Kiểm tra xem document có kết quả hợp lệ không (không chứa '...' hoặc rỗng)"""
    if not doc or not doc.get("ketqua"):
        return False
    
    ketqua = doc.get("ketqua", {})
    
    # Kiểm tra xem có ít nhất một giải có dữ liệu hợp lệ không
    for values in ketqua.values():
        if isinstance(values, list):
            for v in values:
                # Kiểm tra nếu giá trị không rỗng, không phải "...", và có độ dài >= 2
                if v and v != "..." and len(v) >= 2 and v.strip():
                    return True
        else:
            # Kiểm tra giá trị đơn
            if values and values != "..." and len(values) >= 2 and values.strip():
                return True
    return False

def phan_tich_cau_ngang(collection, so_ngay=7):
    """
    Phân tích Cầu Ngang - kiểm tra ĐÚNG: cặp số vị trí X ngày hôm trước có trong KẾT QUẢ ngày hôm sau
    """
    try:
        # Lấy dữ liệu các ngày
        data = get_last_days(collection, so_ngay + 3)
        
        # Lọc chỉ những ngày có kết quả hợp lệ
        valid_data = [d for d in data if has_valid_ketqua(d)]
        
        if len(valid_data) < 2:
            return []
            
        # Sắp xếp theo ngày tăng dần
        valid_data.sort(key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"))
        
        # Chỉ lấy số ngày gần nhất có dữ liệu
        valid_data = valid_data[-min(so_ngay, len(valid_data)):]
        
        if len(valid_data) < 2:
            return []

        last_date = valid_data[-1]["date"]  # Ngày cuối cùng có dữ liệu
        
        # Dictionary để lưu các cầu đang chạy: key = (giai, num_idx, pair_idx)
        running_caus = {}
        final_caus = []
        
        # Duyệt qua từng ngày (bắt đầu từ ngày thứ 2)
        for day_idx in range(1, len(valid_data)):
            current_day = valid_data[day_idx]
            current_date = current_day["date"]
            prev_day = valid_data[day_idx - 1]
            prev_date = prev_day["date"]
            
            print(f"Phân tích ngày: {prev_date} -> {current_date}")
            
            # Dictionary tạm để lưu cầu mới của ngày hiện tại
            new_running_caus = {}
            
            # 1. Xử lý các cầu đang chạy từ ngày trước
            for position_key, cau_info in running_caus.items():
                giai, num_idx, pair_idx = position_key
                last_cap = cau_info['last_cap']
                
                # Kiểm tra xem cặp số này có trong KẾT QUẢ ngày hiện tại không
                found_in_current = is_cap_in_ketqua(last_cap, current_day["ketqua"])
                
                # Nếu tìm thấy, tiếp tục cầu
                if found_in_current:
                    # Lấy cặp số ở CÙNG VỊ TRÍ trong ngày hiện tại
                    current_cap = get_cap_at_position(current_day["ketqua"], giai, num_idx, pair_idx)
                    
                    if current_cap:
                        # Cập nhật thông tin cầu
                        cau_info['history'].append((current_date, current_cap))
                        cau_info['last_cap'] = current_cap
                        cau_info['so_ngay'] += 1
                        
                        new_running_caus[position_key] = cau_info
                        print(f"Cầu tiếp tục: {giai}[{num_idx}][{pair_idx}-{pair_idx+1}], cặp số: {current_cap}, số ngày: {cau_info['so_ngay']}")
            
            # 2. Tìm cầu mới từ ngày hiện tại
            # Tách tất cả cặp số từ ngày trước (prev_date)
            prev_day_caps = extract_all_caps(prev_day)
            
            # Kiểm tra cầu mới: cặp số từ ngày trước có trong KẾT QUẢ ngày hiện tại
            for giai, num_idx, pair_idx, prev_cap in prev_day_caps:
                # Kiểm tra xem cặp số này có trong KẾT QUẢ ngày hiện tại không
                found_in_current = is_cap_in_ketqua(prev_cap, current_day["ketqua"])
                
                # Nếu tìm thấy, tạo cầu mới
                if found_in_current:
                    # Lấy cặp số ở CÙNG VỊ trí trong ngày hiện tại
                    current_cap = get_cap_at_position(current_day["ketqua"], giai, num_idx, pair_idx)
                    
                    if current_cap:
                        # Tạo cầu mới
                        position_key = (giai, num_idx, pair_idx)
                        if position_key not in new_running_caus:
                            new_running_caus[position_key] = {
                                'source': f"{giai}[{num_idx}][{pair_idx}-{pair_idx+1}]",
                                'history': [
                                    (prev_date, prev_cap),
                                    (current_date, current_cap)
                                ],
                                'last_cap': current_cap,
                                'so_ngay': 2
                            }
                            print(f"Cầu mới: {giai}[{num_idx}][{pair_idx}-{pair_idx+1}], cặp số: {prev_cap}->{current_cap}")
            
            # Cập nhật running_caus cho ngày tiếp theo
            running_caus = new_running_caus
        
        # 3. Kiểm tra và lưu các cầu đã kết thúc (ngày cuối)
        for position_key, cau_info in running_caus.items():
            if cau_info['so_ngay'] >= 2 and cau_info['history'][-1][0] == last_date:
                final_caus.append({
                    "source": cau_info['source'],
                    "final": cau_info['last_cap'],
                    "final_reverse": cau_info['last_cap'][1] + cau_info['last_cap'][0],
                    "history": cau_info['history'],
                    "so_ngay": cau_info['so_ngay']
                })
        
        print(f"Tổng số cầu tìm được: {len(final_caus)}")
        return final_caus
        
    except Exception as e:
        print(f"Lỗi trong phân tích cầu ngang: {e}")
        import traceback
        traceback.print_exc()
        return []

def is_cap_in_ketqua(cap, ketqua):
    """
    Kiểm tra xem cặp số có trong 2 SỐ CUỐI của kết quả không
    """
    # Lấy tất cả 2 số cuối từ kết quả
    last_two_digits = get_all_last_two_digits(ketqua)
    
    # Kiểm tra xem cặp số có trong danh sách 2 số cuối không
    return cap in last_two_digits

def get_cap_at_position(ketqua, giai, num_idx, pair_idx):
    """
    Lấy cặp số ở vị trí cụ thể
    """
    if giai in ketqua:
        giai_data = ketqua[giai]
        if isinstance(giai_data, list):
            if num_idx < len(giai_data):
                number = giai_data[num_idx]
            else:
                return None
        else:
            number = giai_data
        
        if number and len(number) > pair_idx + 1:
            return number[pair_idx:pair_idx+2]
    return None

def extract_all_caps(day_data):
    """
    Trích xuất tất cả các cặp số từ một ngày
    """
    caps = []
    ketqua = day_data.get("ketqua", {})
    
    for giai, val in ketqua.items():
        vals = val if isinstance(val, list) else [val]
        
        for num_idx, number in enumerate(vals):
            if not number or number == "..." or len(number) < 2:
                continue
            
            # Tách các cặp số 2 chữ số liền nhau
            for pair_idx in range(len(number) - 1):
                cap = number[pair_idx:pair_idx+2]
                caps.append((giai, num_idx, pair_idx, cap))
    
    return caps

def phan_tich_cau_cheo(collection, so_ngay=7):
    """
    Phân tích cầu chéo - bỏ qua ngày chưa có kết quả đầy đủ
    """
    try:
        # Lấy 10 ngày gần nhất để đảm bảo có đủ 7 ngày có dữ liệu
        data = get_last_days(collection, so_ngay + 3)
        
        # Lọc chỉ những ngày có kết quả hợp lệ (không chứa "..." hoặc rỗng)
        valid_data = [d for d in data if has_valid_ketqua(d)]
        
        if len(valid_data) < 3:
            return {}
            
        valid_data.sort(key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"))

        cau_results = []
        cau_theo_cap_so = defaultdict(list)

        # Chuẩn bị dữ liệu 2 số cuối - CHỈ lấy ngày có dữ liệu
        last_two_digits_per_day = []
        valid_dates = []
        
        for day_data in valid_data:
            ketqua = day_data.get("ketqua", {})
            
            last_two_digits = []
            for values in ketqua.values():
                if isinstance(values, list):
                    for v in values:
                        if v and v != "..." and len(v) >= 2:
                            last_two_digits.append(v[-2:])
                else:
                    if values and values != "..." and len(values) >= 2:
                        last_two_digits.append(values[-2:])
            
            if last_two_digits:  # Chỉ thêm nếu có dữ liệu
                last_two_digits_per_day.append(set(last_two_digits))
                valid_dates.append(day_data["date"])

        if len(valid_dates) < 3:
            return {}

        # Tạo tất cả cầu chéo có thể từ các vị trí khác nhau
        for i in range(len(valid_dates) - 1):  
            ngay_hien_tai = valid_data[i]
            kq1 = ngay_hien_tai.get("ketqua", {})
            
            if not kq1:
                continue

            # Tạo tất cả cặp chéo có thể từ ngày i
            for g1, v1 in kq1.items():
                vals1 = v1 if isinstance(v1, list) else [v1]
                for idx1, so1 in enumerate(vals1):
                    if not so1 or so1 == "...":  # Bỏ qua nếu số rỗng hoặc "..."
                        continue
                    for pos1 in range(len(so1)):
                        for g2, v2 in kq1.items():
                            if g1 == g2:  # Bỏ qua cùng giải
                                continue
                            vals2 = v2 if isinstance(v2, list) else [v2]
                            for idx2, so2 in enumerate(vals2):
                                if not so2 or so2 == "...":  # Bỏ qua nếu số rỗng hoặc "..."
                                    continue
                                for pos2 in range(len(so2)):
                                    # Ghép 2 số từ 2 vị trí khác nhau
                                    cap = so1[pos1] + so2[pos2]
                                    
                                    # Tạo cầu mới
                                    cau = {
                                        "source": f"{g1}[{idx1}][{pos1}] + {g2}[{idx2}][{pos2}]",
                                        "pairs": [cap],
                                        "days": [ngay_hien_tai["date"]],
                                        "alive": True,
                                        "g1": g1, "idx1": idx1, "pos1": pos1,
                                        "g2": g2, "idx2": idx2, "pos2": pos2
                                    }
                                    
                                    # Kiểm tra các ngày tiếp theo (chỉ những ngày có dữ liệu)
                                    for j in range(i + 1, len(valid_dates)):
                                        day_idx = j
                                        # Kiểm tra nếu cặp số có trong kết quả ngày j
                                        if cap in last_two_digits_per_day[day_idx]:
                                            # Lấy cặp số mới từ CÙNG VỊ TRÍ trong ngày j
                                            current_data = valid_data[day_idx]
                                            current_kq = current_data.get("ketqua", {})
                                            
                                            current_so1 = current_kq.get(g1, "")
                                            if isinstance(current_so1, list):
                                                if idx1 < len(current_so1):
                                                    current_so1 = current_so1[idx1]
                                                else:
                                                    cau["alive"] = False
                                                    break
                                            if not current_so1 or current_so1 == "...":
                                                cau["alive"] = False
                                                break
                                            
                                            current_so2 = current_kq.get(g2, "")
                                            if isinstance(current_so2, list):
                                                if idx2 < len(current_so2):
                                                    current_so2 = current_so2[idx2]
                                                else:
                                                    cau["alive"] = False
                                                    break
                                            if not current_so2 or current_so2 == "...":
                                                cau["alive"] = False
                                                break
                                            
                                            if len(current_so1) > pos1 and len(current_so2) > pos2:
                                                cap = current_so1[pos1] + current_so2[pos2]
                                                cau["pairs"].append(cap)
                                                cau["days"].append(current_data["date"])
                                            else:
                                                cau["alive"] = False
                                                break
                                        else:
                                            cau["alive"] = False
                                            break
                                    
                                    # Nếu cầu sống đến ngày cuối
                                    if cau["alive"] and len(cau["days"]) >= 2:
                                        final_result = {
                                            "final": cau['pairs'][-1],
                                            "final_reverse": cau['pairs'][-1][1] + cau['pairs'][-1][0],
                                            "history": list(zip(cau['days'], cau['pairs'])),
                                            "source": cau['source']
                                        }
                                        cau_theo_cap_so[final_result['final']].append(final_result)
                                        cau_results.append(final_result)

        return dict(cau_theo_cap_so)
        
    except Exception as e:
        print(f"Lỗi phân tích cầu chéo: {e}")
        import traceback
        traceback.print_exc()
        return {}

def group_cau_by_number(cau_list):
    """
    Nhóm các cầu theo số cuối cùng
    """
    from collections import defaultdict
    grouped = defaultdict(list)
    
    for cau in cau_list:
        num = cau["final"]
        grouped[num].append(cau)
    
    # Trả về dạng [{"num": "97", "caus": [c1, c2,...]}, ...]
    return [{"num": num, "caus": caus} for num, caus in grouped.items()]


def phan_tich_theo_thu(collection, so_ngay=30):
    """
    Phân tích XSMB theo thứ - CHỈ quan tâm có về hay không trong ngày
    """
    try:
        # Lấy 30 ngày gần nhất
        data = get_last_days(collection, so_ngay)
        data.reverse()

        thu_labels = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]

        # Dictionary để lưu trữ: mỗi thứ -> set các số đã về trong mỗi ngày
        thu_so_set = {i: set() for i in range(7)}  # Set các số đã về
        thu_ngay_so = {i: defaultdict(set) for i in range(7)}  # Số -> set các ngày đã về
        thu_day_count = defaultdict(int)  # Số ngày có dữ liệu của mỗi thứ

        for doc in data:
            try:
                ngay_str = doc.get("date", "")
                if not ngay_str:
                    continue
                    
                ngay = datetime.strptime(ngay_str, "%d-%m-%Y")
                thu = ngay.weekday()
                thu_day_count[thu] += 1

                # Lấy tất cả 2 số cuối từ ketqua (chỉ lấy unique trong ngày)
                so_trong_ngay = set()
                ketqua = doc.get("ketqua", {})
                
                for giai, values in ketqua.items():
                    if isinstance(values, list):
                        for v in values:
                            if v and len(v) >= 2:
                                so_trong_ngay.add(v[-2:])
                    else:
                        if values and len(values) >= 2:
                            so_trong_ngay.add(values[-2:])

                # Cập nhật: mỗi số chỉ tính 1 lần cho mỗi ngày
                for so in so_trong_ngay:
                    thu_so_set[thu].add(so)
                    thu_ngay_so[thu][so].add(ngay_str)

            except Exception as e:
                print(f"Lỗi xử lý ngày {doc.get('date')}: {e}")
                continue

        # Tính xác suất: số ngày số đó về / tổng số ngày của thứ
        ket_qua = {}
        for thu in range(7):
            tong_ngay = thu_day_count[thu]
            if tong_ngay == 0:
                ket_qua[thu_labels[thu]] = {
                    "so": "N/A",
                    "xac_suat": 0,
                    "ngay_ve": [],
                    "tong_so_ngay": 0
                }
                continue
            
            # Tạo list các số và tỷ lệ về
            so_xac_suat = []
            for so in thu_so_set[thu]:
                so_ngay_ve = len(thu_ngay_so[thu][so])
                xac_suat = round(so_ngay_ve / tong_ngay * 100, 2)
                so_xac_suat.append((so, so_ngay_ve, xac_suat, thu_ngay_so[thu][so]))
            
            # Sắp xếp theo xác suất giảm dần
            so_xac_suat.sort(key=lambda x: (-x[2], -x[1]))  # Xác suất cao nhất trước
            
            ket_qua[thu_labels[thu]] = {
                "top_3": [],
                "tong_so_ngay": tong_ngay
            }
            
            # Lấy top 3 số có xác suất cao nhất
            for so, so_ngay_ve, xac_suat, ngay_ve_set in so_xac_suat[:3]:
                ket_qua[thu_labels[thu]]["top_3"].append({
                    "so": so,
                    "so_lan": so_ngay_ve,  # Số ngày đã về (không phải số lần về)
                    "xac_suat": xac_suat,
                    "ngay_ve": sorted(ngay_ve_set)  # Danh sách ngày đã về
                })

        return ket_qua
        
    except Exception as e:
        print(f"Lỗi trong phân tích theo thứ: {e}")
        import traceback
        traceback.print_exc()
        return {}

def phan_tich_lap_deu_chi_tiet(collection, so_ngay=30, gioi_han_ngay=7):
    """
    Phân tích chi tiết chu kỳ các số
    """
    try:
        data = get_last_days(collection, so_ngay)
        data.reverse()  # đảo lại theo ngày tăng dần (từ cũ → mới)

        if not data:
            return {}
        last_date = datetime.strptime(data[-1]["date"], "%d-%m-%Y")
            
        data.sort(key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"))
        
        so_history = {f"{i:02d}": [] for i in range(100)}
        
        for doc in data:
            ngay = doc["date"]
            ketqua = doc.get("ketqua", {})
            
            all_last_two = []
            for values in ketqua.values():
                if isinstance(values, list):
                    for v in values:
                        if len(v) >= 2:
                            all_last_two.append(v[-2:])
                else:
                    if len(values) >= 2:
                        all_last_two.append(values[-2:])
            
            for so in set(all_last_two):  # Chỉ tính mỗi số 1 lần/ngày
                if so in so_history:
                    so_history[so].append(ngay)
        
        ket_qua = {}
        
        for so, ngay_list in so_history.items():
            if len(ngay_list) < 3:
                continue
                
            ngay_list.sort(key=lambda x: datetime.strptime(x, "%d-%m-%Y"))
            
            # Ngày gần nhất con số xuất hiện
            ngay_gan_nhat = datetime.strptime(ngay_list[-1], "%d-%m-%Y")
            
            # Nếu ngày gần nhất cách ngày cuối cùng > giới hạn thì bỏ qua
            if (last_date - ngay_gan_nhat).days > gioi_han_ngay:
                continue
            # Phân tích nhiều loại chu kỳ
            patterns = phan_tich_chu_ky(ngay_list)
            
            if patterns:
                ket_qua[so] = {
                    "patterns": patterns,
                    "lich_su": ngay_list,
                    "so_lan": len(ngay_list),
                    "ngay_gan_nhat": ngay_list[-1]
                }
        
        return dict(sorted(ket_qua.items(), key=lambda x: x[1]["so_lan"], reverse=True))
        
    except Exception as e:
        print(f"Lỗi phân tích lặp đều chi tiết: {e}")
        return {}

def phan_tich_chu_ky(ngay_list):
    """
    Phân tích các chu kỳ có thể từ danh sách ngày
    """
    if len(ngay_list) < 3:
        return []
    
    # Chuyển sang datetime object
    dates = [datetime.strptime(ngay, "%d-%m-%Y") for ngay in ngay_list]
    dates.sort()
    
    # Tính khoảng cách
    gaps = []
    for i in range(1, len(dates)):
        gap = (dates[i] - dates[i-1]).days
        gaps.append(gap)
    
    # Tìm chu kỳ phổ biến
    from collections import Counter
    gap_counter = Counter(gaps)
    
    patterns = []
    
    # Chu kỳ hoàn toàn đều
    if len(set(gaps)) == 1:
        patterns.append({
            "chu_ky": gaps[0],
            "kieu": "hoan_toan_deu",
            "do_chinh_xac": 100,
            "so_lan": len(gaps)
        })
        return patterns
    
    # Các chu kỳ có thể
    for gap, count in gap_counter.most_common():
        if count >= 2:  # Ít nhất 2 lần cùng chu kỳ
            do_chinh_xac = round(count / len(gaps) * 100, 1)
            patterns.append({
                "chu_ky": gap,
                "kieu": "phan_bo_deu",
                "do_chinh_xac": do_chinh_xac,
                "so_lan": count
            })
    
    return patterns

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