# file: ml_predictor.py
import pandas as pd
from datetime import datetime
from pymongo import MongoClient
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

# import các phân tích / helper từ module của bạn
from .phan_tich import (
    get_last_days,
    phan_tich_cau_ngang,
    phan_tich_cau_cheo,
    get_all_last_two_digits,
    phan_tich_lo_roi,
    extract_all_caps,
    get_cap_at_position,
)

def has_number_in_day(number_str, day_data):
    """Kiểm tra số có xuất hiện trong kết quả ngày đó không"""
    ketqua = day_data.get("ketqua", {})
    all_last_two = get_all_last_two_digits(ketqua)
    return number_str in all_last_two

def safe_int(s, default=0):
    try:
        return int(s)
    except:
        return default

def _compute_ngang_strength(giai, num_idx, pair_idx, start_idx, data):
    """
    Tính strength cho 1 cầu ngang: bắt đầu từ start_idx (đã thấy ở ngày start_idx),
    tiếp tục đếm các ngày liên tiếp sau đó mà cap ở cùng vị trí còn tồn tại.
    """
    strength = 1
    for j in range(start_idx + 1, len(data)):
        try:
            cap = get_cap_at_position(data[j].get("ketqua", {}), giai, num_idx, pair_idx)
        except Exception:
            cap = None
        if cap and cap.strip():
            strength += 1
        else:
            break
    return strength

def _compute_cheo_strength(g1, idx1, pos1, g2, idx2, pos2, start_idx, data, target):
    """
    Tính strength cho 1 cầu chéo: chỉ đếm các ngày liên tiếp mà cặp chéo vẫn tạo ra số.
    """
    strength = 1
    n_days = len(data)

    # lấy giá trị cap gốc của start_idx - 1
    prev_doc = data[start_idx - 1]
    try:
        so1 = get_cap_at_position(prev_doc.get("ketqua", {}), g1, idx1, pos1)
        so2 = get_cap_at_position(prev_doc.get("ketqua", {}), g2, idx2, pos2)
    except Exception:
        return 0

    if not so1 or not so2:
        return 0

    # ký tự để so sánh tạo cầu chéo
    try:
        target = so1[pos1] + so2[pos2]
    except Exception:
        return 0

    # kiểm tra từng ngày tiếp theo
    for j in range(start_idx, n_days):
        kq = data[j].get("ketqua", {})
        try:
            next_g1 = get_cap_at_position(kq, g1, idx1, pos1)
            next_g2 = get_cap_at_position(kq, g2, idx2, pos2)
        except Exception:
            break

        if not next_g1 or not next_g2:
            break

        try:
            candidate = next_g1[pos1] + next_g2[pos2]
        except Exception:
            break

        if candidate == target:
            strength += 1
        else:
            break

    return strength

def build_features_and_label(collection, so_ngay=30):
    """
    Sinh feature nâng cao cho 00-99 dựa trên so_ngay ngày gần nhất.
    Trả về: df_train, df_predict, predict_date
    """
    # Lấy dữ liệu
    data = get_last_days(collection, so_ngay)
    data = [d for d in data if d.get("date_obj")]
    data.sort(key=lambda x: x["date_obj"])  # từ cũ -> mới

    if len(data) < 8:
        print("❌ Không đủ dữ liệu để build features (cần >=8 ngày có kết quả).")
        return pd.DataFrame(), pd.DataFrame(), None

    # Precompute expensive analyses ONCE (dùng để các feature lô rơi / tổng quan nếu cần)
    try:
        lo_roi_analysis = phan_tich_lo_roi(collection, so_ngay=so_ngay) or {}
    except Exception as e:
        print("⚠️ Lỗi khi chạy phan_tich_lo_roi:", e)
        lo_roi_analysis = {}

    all_rows = []
    # Build training samples. For each day i (từ thứ 7 trở đi), label là ngày i+1
    for i in range(7, len(data) - 1):
        cur_doc = data[i]
        next_doc = data[i + 1]
        current_date = cur_doc["date"]
        next_date = next_doc["date"]

        previous_7_days = data[i - 7:i]
        previous_14_days = data[i - 14:i] if i >= 14 else data[max(0, i-14):i]
        previous_30_days = data[:i]

        # chuẩn bị các caps/positions từ ngày current để kiểm tra ngang/chéo sang next
        prev_caps = extract_all_caps(cur_doc)  # list of (giai, num_idx, pair_idx, cap)
        next_last_twos = set(get_all_last_two_digits(next_doc.get("ketqua", {})))

        # tạo map nhanh prev caps theo cap -> list of (giai, num_idx, pair_idx)
        prev_caps_map = {}
        for g, num_idx, pair_idx, cap in prev_caps:
            prev_caps_map.setdefault(cap, []).append((g, num_idx, pair_idx))

        for n in range(100):
            number_str = f"{n:02d}"

            # BASIC
            freq_7days = sum(1 for d in previous_7_days if has_number_in_day(number_str, d))
            freq_prev_day = 1 if previous_7_days and has_number_in_day(number_str, previous_7_days[-1]) else 0

            # === compute is_cau_ngang and cau_ngang_strength using prev_caps -> next_doc ===
            is_ngang = 0
            cau_ngang_strength = 0
            # For ngang: find any prev cap whose corresponding position in next_doc equals number_str
            for (g, num_idx, pair_idx, cap) in prev_caps:
                # find cap at same position in next_doc
                try:
                    cap_next = get_cap_at_position(next_doc.get("ketqua", {}), g, num_idx, pair_idx)
                except Exception:
                    cap_next = None
                if cap_next == number_str:
                    is_ngang = 1
                    # compute how many consecutive days it continues (strength), starting at next index (i+1)
                    cau_ngang_strength = _compute_ngang_strength(g, num_idx, pair_idx, i+1, data)
                    break

            # === compute is_cau_cheo and cau_cheo_strength using cross pairs from prev_doc -> next_doc ===
            is_cheo = 0
            cau_cheo_strength = 0
            # build all possible cross pairs from prev_doc (two different positions from prev_doc)
            # We'll only check combinations where result at next_doc same pos-pair equals number_str
            # Note: this loops over O(k^2) where k ~ number of extracted fields (usually small)
            k = len(prev_caps)
            for a in range(k):
                g1, idx1, pos1, so1 = prev_caps[a]
                for b in range(k):
                    g2, idx2, pos2, so2 = prev_caps[b]
                    if g1 == g2 and idx1 == idx2 and pos1 == pos2:
                        continue  # must be different positions (chéo)
                    # build cap from prev: so1[pos1] + so2[pos2]
                    try:
                        if len(so1) > 0 and len(so2) > 0:
                            cap_prev = so1[pos1] + so2[pos2]
                        else:
                            continue
                    except Exception:
                        continue

                    # Now check whether next_doc produces cap at same (g1,pos1) + (g2,pos2)
                    try:
                        next_g1 = get_cap_at_position(next_doc.get("ketqua", {}), g1, idx1, pos1)
                        next_g2 = get_cap_at_position(next_doc.get("ketqua", {}), g2, idx2, pos2)
                    except Exception:
                        next_g1 = next_g2 = None

                    if next_g1 and next_g2 and len(next_g1) >= 1 and len(next_g2) >= 1:
                        cap_next = next_g1[0] + next_g2[0] if len(next_g1) >= 1 and len(next_g2) >= 1 else None
                        # but phan_tich_cau_cheo uses concatenation of characters at those positions,
                        # better to compare full 2-char pairs generated in that function:
                        # build exactly as they did: take char at pos1 from current so1 and char at pos2 from current so2.
                        try:
                            # build cap_next in same way:
                            cap_next_full = next_g1[pos1] + next_g2[pos2] if len(next_g1) > pos1 and len(next_g2) > pos2 else None
                        except Exception:
                            cap_next_full = None

                        if cap_next_full == number_str:
                            is_cheo = 1
                            target = cap_next_full
                            cau_cheo_strength = _compute_cheo_strength(g1, idx1, pos1, g2, idx2, pos2, i+1, data, target)
                            break
                if is_cheo:
                    break

            # ADVANCED FREQUENCIES
            freq_3days = sum(1 for d in previous_7_days[-3:] if has_number_in_day(number_str, d))
            freq_14days = sum(1 for d in previous_14_days if has_number_in_day(number_str, d))
            freq_30days = sum(1 for d in previous_30_days if has_number_in_day(number_str, d))
            freq_ratio_7days = freq_7days / 7.0
            freq_ratio_30days = freq_30days / len(previous_30_days) if previous_30_days else 0.0

            # APPEARANCE HISTORY on previous_30_days
            appearance_indices = []
            for idx, dd in enumerate(previous_30_days):
                if has_number_in_day(number_str, dd):
                    appearance_indices.append(idx)

            if len(appearance_indices) >= 2:
                gaps = [appearance_indices[j] - appearance_indices[j - 1] for j in range(1, len(appearance_indices))]
                avg_gap = sum(gaps) / len(gaps)
                min_gap = min(gaps)
                max_gap = max(gaps)
                last_gap = gaps[-1]
                consecutive_count = sum(1 for g in gaps if g == 1)
            else:
                avg_gap = min_gap = max_gap = last_gap = len(previous_30_days)
                consecutive_count = 0

            days_since_last = (len(previous_30_days) - 1 - appearance_indices[-1]) if appearance_indices else len(previous_30_days)

            # DAY OF WEEK one-hot for current date
            try:
                dow = datetime.strptime(current_date, "%d-%m-%Y").weekday()
            except:
                dow = None
            is_monday = 1 if dow == 0 else 0
            is_tuesday = 1 if dow == 1 else 0
            is_wednesday = 1 if dow == 2 else 0
            is_thursday = 1 if dow == 3 else 0
            is_friday = 1 if dow == 4 else 0
            is_saturday = 1 if dow == 5 else 0
            is_sunday = 1 if dow == 6 else 0

            # CHAM & TONG features
            cham_dau = safe_int(number_str[0])
            cham_cuoi = safe_int(number_str[1])
            tong = cham_dau + cham_cuoi
            tong_cham = tong % 10
            tong_chan = 1 if tong % 2 == 0 else 0
            tong_le = 1 if tong % 2 == 1 else 0
            tong_lon = 1 if tong > 9 else 0
            tong_nho = 1 if tong <= 9 else 0

            # CAU STRENGTH / IN ANY CAU
            in_any_cau = 1 if (is_ngang or is_cheo) else 0

            # LO ROI features
            is_lo_roi_ung_vien = 0
            lo_roi_ty_le = 0
            for uv in lo_roi_analysis.get("ung_vien", []):
                if uv.get("so") and uv.get("so") == number_str:
                    is_lo_roi_ung_vien = 1
                    lo_roi_ty_le = uv.get("ty_le", 0)
                    break
            days_since_roi_db = lo_roi_analysis.get("db", {}).get("last_gap", len(previous_30_days))
            days_since_roi_nhieu = lo_roi_analysis.get("nhieu_nhay", {}).get("last_gap", len(previous_30_days))

            # LABEL: có về ngày next_date không?
            label = 1 if has_number_in_day(number_str, next_doc) else 0

            row = {
                "current_date": current_date,
                "next_date": next_date,
                "number": number_str,
                # basic
                "freq_7days": freq_7days,
                "freq_prev_day": freq_prev_day,
                # advanced freq
                "freq_3days": freq_3days,
                "freq_14days": freq_14days,
                "freq_30days": freq_30days,
                "freq_ratio_7days": freq_ratio_7days,
                "freq_ratio_30days": freq_ratio_30days,
                # gaps / seq
                "avg_gap": avg_gap,
                "min_gap": min_gap,
                "max_gap": max_gap,
                "last_gap": last_gap,
                "consecutive_count": consecutive_count,
                "days_since_last": days_since_last,
                # day of week
                "is_monday": is_monday,
                "is_tuesday": is_tuesday,
                "is_wednesday": is_wednesday,
                "is_thursday": is_thursday,
                "is_friday": is_friday,
                "is_saturday": is_saturday,
                "is_sunday": is_sunday,
                # cham/tong
                "cham_dau": cham_dau,
                "cham_cuoi": cham_cuoi,
                "tong": tong,
                "tong_cham": tong_cham,
                "tong_chan": tong_chan,
                "tong_le": tong_le,
                "tong_lon": tong_lon,
                "tong_nho": tong_nho,
                # cau
                "is_cau_ngang": is_ngang,
                "is_cau_cheo": is_cheo,
                "cau_ngang_strength": cau_ngang_strength,
                "cau_cheo_strength": cau_cheo_strength,
                "in_any_cau": in_any_cau,
                # lo roi
                "is_lo_roi_ung_vien": is_lo_roi_ung_vien,
                "lo_roi_ty_le": lo_roi_ty_le,
                "days_since_roi_db": days_since_roi_db,
                "days_since_roi_nhieu": days_since_roi_nhieu,
                # label
                "label": label,
            }

            all_rows.append(row)

    # Build predict set for next day (based on last day in `data`)
    last_doc = data[-1]
    predict_date = (last_doc["date_obj"] + pd.Timedelta(days=1)).strftime("%d-%m-%Y")
    previous_7_days = data[-7:] if len(data) >= 7 else data
    previous_14_days = data[-14:] if len(data) >= 14 else data
    previous_30_days = data

    predict_rows = []
    # For predict, we need to check "is_cau_ngang/is_cau_cheo" using last_doc -> (predict day)
    prev_caps = extract_all_caps(last_doc)
    for n in range(100):
        number_str = f"{n:02d}"

        freq_7days = sum(1 for d in previous_7_days if has_number_in_day(number_str, d))
        freq_prev_day = 1 if previous_7_days and has_number_in_day(number_str, previous_7_days[-1]) else 0

        # For predict we will mark is_ngang/is_cheo if we can find that next-day (unknown) would be produced.
        # We cannot confirm since future unknown; but we can flag candidate if preconditions exist in last_doc.
        # Strategy: mark is_ngang candidate if number_str equals cap produced by get_cap_at_position in the *next day* —
        # but next day unknown; instead mark is candidate 1 if some prev cap in last_doc could produce number_str pattern
        # (i.e., there exists (g,num_idx,pair_idx) such that last_doc cap at that pos forms X and number_str equals X)
        # This is approximate but acceptable for ML features.
        is_ngang = 0
        cau_ngang_strength = 0
        for g, num_idx, pair_idx, cap in prev_caps:
            # if cap itself equals number_str (means if next day had same position char pair -> candidate)
            if cap == number_str:
                is_ngang = 1
                cau_ngang_strength = 1  # unknown future continuation
                break

        is_cheo = 0
        cau_cheo_strength = 0
        k = len(prev_caps)
        for a in range(k):
            g1, idx1, pos1, so1 = prev_caps[a]
            for b in range(k):
                g2, idx2, pos2, so2 = prev_caps[b]
                if g1 == g2 and idx1 == idx2 and pos1 == pos2:
                    continue
                try:
                    cap_prev = so1[pos1] + so2[pos2]
                except Exception:
                    continue
                if cap_prev == number_str:
                    is_cheo = 1
                    cau_cheo_strength = 1
                    break
            if is_cheo:
                break

        freq_3days = sum(1 for d in previous_7_days[-3:] if has_number_in_day(number_str, d))
        freq_14days = sum(1 for d in previous_14_days if has_number_in_day(number_str, d))
        freq_30days = sum(1 for d in previous_30_days if has_number_in_day(number_str, d))
        freq_ratio_7days = freq_7days / 7.0
        freq_ratio_30days = freq_30days / len(previous_30_days) if previous_30_days else 0.0

        appearance_indices = []
        for idx, dd in enumerate(previous_30_days):
            if has_number_in_day(number_str, dd):
                appearance_indices.append(idx)
        if len(appearance_indices) >= 2:
            gaps = [appearance_indices[j] - appearance_indices[j - 1] for j in range(1, len(appearance_indices))]
            avg_gap = sum(gaps) / len(gaps)
            min_gap = min(gaps)
            max_gap = max(gaps)
            last_gap = gaps[-1]
            consecutive_count = sum(1 for g in gaps if g == 1)
        else:
            avg_gap = min_gap = max_gap = last_gap = len(previous_30_days)
            consecutive_count = 0
        days_since_last = (len(previous_30_days) - 1 - appearance_indices[-1]) if appearance_indices else len(previous_30_days)

        try:
            dow = datetime.strptime(predict_date, "%d-%m-%Y").weekday()
        except:
            dow = None
        is_monday = 1 if dow == 0 else 0
        is_tuesday = 1 if dow == 1 else 0
        is_wednesday = 1 if dow == 2 else 0
        is_thursday = 1 if dow == 3 else 0
        is_friday = 1 if dow == 4 else 0
        is_saturday = 1 if dow == 5 else 0
        is_sunday = 1 if dow == 6 else 0

        cham_dau = safe_int(number_str[0])
        cham_cuoi = safe_int(number_str[1])
        tong = cham_dau + cham_cuoi
        tong_cham = tong % 10
        tong_chan = 1 if tong % 2 == 0 else 0
        tong_le = 1 if tong % 2 == 1 else 0
        tong_lon = 1 if tong > 9 else 0
        tong_nho = 1 if tong <= 9 else 0

        in_any_cau = 1 if (is_ngang or is_cheo) else 0

        is_lo_roi_ung_vien = 0
        lo_roi_ty_le = 0
        for uv in lo_roi_analysis.get("ung_vien", []):
            if uv.get("so") and uv.get("so") == number_str:
                is_lo_roi_ung_vien = 1
                lo_roi_ty_le = uv.get("ty_le", 0)
                break
        days_since_roi_db = lo_roi_analysis.get("db", {}).get("last_gap", len(previous_30_days))
        days_since_roi_nhieu = lo_roi_analysis.get("nhieu_nhay", {}).get("last_gap", len(previous_30_days))

        predict_rows.append({
            "current_date": current_date,
            "next_date": next_date,
            "number": number_str,
            "freq_7days": freq_7days,
            "freq_prev_day": freq_prev_day,
            "is_cau_ngang": is_ngang,
            "is_cau_cheo": is_cheo,
            "freq_3days": freq_3days,
            "freq_14days": freq_14days,
            "freq_30days": freq_30days,
            "freq_ratio_7days": freq_ratio_7days,
            "freq_ratio_30days": freq_ratio_30days,
            "avg_gap": avg_gap,
            "min_gap": min_gap,
            "max_gap": max_gap,
            "last_gap": last_gap,
            "consecutive_count": consecutive_count,
            "days_since_last": days_since_last,
            "is_monday": is_monday,
            "is_tuesday": is_tuesday,
            "is_wednesday": is_wednesday,
            "is_thursday": is_thursday,
            "is_friday": is_friday,
            "is_saturday": is_saturday,
            "is_sunday": is_sunday,
            "cham_dau": cham_dau,
            "cham_cuoi": cham_cuoi,
            "tong": tong,
            "tong_cham": tong_cham,
            "tong_chan": tong_chan,
            "tong_le": tong_le,
            "tong_lon": tong_lon,
            "tong_nho": tong_nho,
            "cau_ngang_strength": cau_ngang_strength,
            "cau_cheo_strength": cau_cheo_strength,
            "in_any_cau": in_any_cau,
            "is_lo_roi_ung_vien": is_lo_roi_ung_vien,
            "lo_roi_ty_le": lo_roi_ty_le,
            "days_since_roi_db": days_since_roi_db,
            "days_since_roi_nhieu": days_since_roi_nhieu,
        })

    df_train = pd.DataFrame(all_rows)
    df_predict = pd.DataFrame(predict_rows)

    # Fill NaN / types (infer_objects trước rồi fillna -> tránh warning downcast)
    df_train = df_train.infer_objects(copy=False).fillna(0)
    df_predict = df_predict.infer_objects(copy=False).fillna(0)

    # lưu ra CSV để bạn inspect
    df_train.to_csv("train_samples.csv", index=False, encoding="utf-8")
    df_predict.to_csv("predict_samples.csv", index=False, encoding="utf-8")

    print(f"✅ Đã tạo {len(df_train)} samples train với {len(df_train.columns)} features")
    print(f"✅ Đã tạo {len(df_predict)} samples predict — predict_date = {predict_date}")
    print("✅ Đã lưu train_samples.csv và predict_samples.csv")

    return df_train, df_predict, predict_date

def du_doan_ml(collection, so_du_doan=10, so_ngay=30):
    """Hàm để Flask gọi dự đoán ML"""
    df_train, df_predict, predict_date = build_features_and_label(collection, so_ngay=so_ngay)

    if df_train.empty or df_predict.empty or predict_date is None:
        return {"error": "❌ Không đủ dữ liệu để train hoặc predict"}

    features = [
        "freq_7days", "freq_prev_day", "freq_3days", "freq_14days", "freq_30days",
        "freq_ratio_7days", "freq_ratio_30days",
        "avg_gap", "min_gap", "max_gap", "last_gap", "consecutive_count", "days_since_last",
        "is_cau_ngang", "is_cau_cheo", "cau_ngang_strength", "cau_cheo_strength", "in_any_cau",
        "is_lo_roi_ung_vien", "lo_roi_ty_le", "days_since_roi_db", "days_since_roi_nhieu",
        "cham_dau", "cham_cuoi", "tong", "tong_chan", "tong_le", "tong_lon", "tong_nho",
        "is_monday", "is_tuesday", "is_wednesday", "is_thursday", "is_friday", "is_saturday", "is_sunday",
    ]

    features = [f for f in features if f in df_train.columns and f in df_predict.columns]
    if not features:
        return {"error": "❌ Không có feature hợp lệ để train"}

    X_train = df_train[features].astype(float)
    y_train = df_train["label"].astype(int)
    X_pred = df_predict[features].astype(float)

    lr_pipeline = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500))
    rf_pipeline = make_pipeline(StandardScaler(), RandomForestClassifier(n_estimators=100, random_state=42))

    try:
        lr_pipeline.fit(X_train, y_train)
        rf_pipeline.fit(X_train, y_train)
    except Exception as e:
        return {"error": f"❌ Lỗi khi train model: {e}"}

    try:
        prob_lr = lr_pipeline.predict_proba(X_pred)[:, 1]
        prob_rf = rf_pipeline.predict_proba(X_pred)[:, 1]
    except Exception as e:
        return {"error": f"❌ Lỗi khi predict: {e}"}

    df_predict = df_predict.copy()
    df_predict["prob_lr"] = prob_lr
    df_predict["prob_rf"] = prob_rf
    df_predict["prob_avg"] = df_predict[["prob_lr", "prob_rf"]].mean(axis=1)

    df_result = df_predict.sort_values("prob_avg", ascending=False).reset_index(drop=True)
    top_k = df_result.head(so_du_doan)

    du_doan = []
    for _, row in top_k.iterrows():
        du_doan.append({"so": row["number"], "xac_suat": float(row["prob_avg"])})

    return {
        "predict_date": predict_date,
        "du_doan": du_doan
    }

def main():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["admin"]
    collection = db["kq_xs"]

    print("⚙️ Lấy dữ liệu và sinh feature...")
    res = du_doan_ml(collection, so_du_doan=10, so_ngay=30)
    if "error" in res:
        print(res["error"])
        return

    print(f"🔮 Dự đoán cho ngày {res['predict_date']}:")
    for item in res["du_doan"]:
        print(f"  - {item['so']}  (p={item['xac_suat']:.4f})")

if __name__ == "__main__":
    main()
