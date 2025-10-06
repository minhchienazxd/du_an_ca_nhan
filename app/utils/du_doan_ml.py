# file: ml_predictor.py
import pandas as pd
from datetime import datetime, timedelta
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

def get_training_data(data):
    """
    Lọc chỉ những ngày có kết quả hợp lệ để training
    Trả về: danh sách các ngày đã có kết quả
    """
    valid_data = [d for d in data if has_valid_ketqua(d)]
    print(f"📊 Dữ liệu training: {len(valid_data)}/{len(data)} ngày có kết quả hợp lệ")
    
    # In ra các ngày có kết quả để debug
    if valid_data:
        dates = [d["date"] for d in valid_data]
        print(f"📅 Các ngày có kết quả: {dates}")
    
    return valid_data

def get_prediction_date(training_data):
    """
    Xác định ngày cần dự đoán dựa trên dữ liệu training
    """
    if not training_data:
        return None
    
    last_training_date = training_data[-1]["date"]
    last_date_obj = training_data[-1]["date_obj"]
    
    # Ngày dự đoán là ngày tiếp theo sau ngày cuối cùng có kết quả
    predict_date = (last_date_obj + timedelta(days=1)).strftime("%d-%m-%Y")
    
    print(f"🎯 Dự đoán: {last_training_date} → {predict_date}")
    return predict_date

def safe_int(s, default=0):
    try:
        return int(s)
    except:
        return default

def build_features_and_label(collection, so_ngay=30):
    """
    Sinh feature nâng cao cho 00-99 dựa trên so_ngay ngày gần nhất.
    Trả về: df_train, df_predict, predict_date
    """
    # Lấy dữ liệu thô
    raw_data = get_last_days(collection, so_ngay)
    raw_data = [d for d in raw_data if d.get("date_obj")]
    raw_data.sort(key=lambda x: x["date_obj"])  # từ cũ -> mới

    print(f"📦 Dữ liệu thô: {len(raw_data)} ngày")
    
    # CHỈ dùng ngày có kết quả hợp lệ để training
    training_data = get_training_data(raw_data)
    
    if len(training_data) < 8:
        print("❌ Không đủ dữ liệu để build features (cần >=8 ngày có kết quả).")
        return pd.DataFrame(), pd.DataFrame(), None

    # Xác định ngày cần dự đoán
    predict_date = get_prediction_date(training_data)
    if not predict_date:
        print("❌ Không thể xác định ngày dự đoán")
        return pd.DataFrame(), pd.DataFrame(), None

    # Precompute expensive analyses ONCE (dùng để các feature lô rơi / tổng quan nếu cần)
    try:
        lo_roi_analysis = phan_tich_lo_roi(collection, so_ngay=so_ngay) or {}
    except Exception as e:
        print("⚠️ Lỗi khi chạy phan_tich_lo_roi:", e)
        lo_roi_analysis = {}

    all_rows = []
    # Build training samples. For each day i (từ thứ 7 trở đi), label là ngày i+1
    # CHỈ dùng training_data (đã có kết quả)
    for i in range(7, len(training_data) - 1):
        cur_doc = training_data[i]
        next_doc = training_data[i + 1]
        current_date = cur_doc["date"]
        next_date = next_doc["date"]

        # SỬA: previous days phải lấy từ training_data, không phải raw_data
        previous_7_days = training_data[i - 7:i]
        previous_14_days = training_data[i - 14:i] if i >= 14 else training_data[max(0, i-14):i]
        previous_30_days = training_data[:i]

        # chuẩn bị các caps/positions từ ngày current để kiểm tra ngang/chéo sang next
        # SỬA: chỉ dùng training_data để phân tích cầu
        analysis_data = training_data[max(0, i-7):i+2]
        cau_ngang_results = phan_tich_cau_ngang(analysis_data)
        cau_cheo_results = phan_tich_cau_cheo(analysis_data)

        for n in range(100):
            number_str = f"{n:02d}"

            # BASIC
            freq_7days = sum(1 for d in previous_7_days if has_number_in_day(number_str, d))
            freq_prev_day = 1 if previous_7_days and has_number_in_day(number_str, previous_7_days[-1]) else 0

            # === compute is_cau_ngang and cau_ngang_strength using prev_caps -> next_doc ===
            is_ngang = 0
            cau_ngang_strength = 0
            for c in cau_ngang_results:
                if c.get("final") == number_str:
                    is_ngang = 1
                    cau_ngang_strength = len(c.get("history", []))
                    break

            # === compute is_cau_cheo and cau_cheo_strength using cross pairs from prev_doc -> next_doc ===
            is_cheo = 0
            cau_cheo_strength = 0
            if isinstance(cau_cheo_results, dict):
                for cap_so, caus in cau_cheo_results.items():
                    if cap_so == number_str:
                        is_cheo = 1
                        cau_cheo_strength = len(caus)
                        break
            else:
                for c in cau_cheo_results:
                    if c.get("final") == number_str:
                        is_cheo = 1
                        cau_cheo_strength = len(c.get("history", []))
                        break
            
            in_any_cau = 1 if (is_ngang or is_cheo) else 0

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
                last_gap = gaps[-1] if gaps else len(previous_30_days)
                consecutive_count = sum(1 for g in gaps if g == 1)
            else:
                avg_gap = min_gap = max_gap = last_gap = len(previous_30_days)
                consecutive_count = 0

            days_since_last = (len(previous_30_days) - 1 - appearance_indices[-1]) if appearance_indices else len(previous_30_days)

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

    # Build predict set for prediction date
    # SỬA: Dùng training_data (đã có kết quả) để build features cho prediction
    last_training_doc = training_data[-1]
    current_date_for_prediction = last_training_doc["date"]
    
    previous_7_days = training_data[-7:] if len(training_data) >= 7 else training_data
    previous_14_days = training_data[-14:] if len(training_data) >= 14 else training_data
    previous_30_days = training_data
    
    # SỬA: Phân tích cầu chỉ dùng training_data
    cau_ngang_results = phan_tich_cau_ngang(training_data[-7:])
    cau_cheo_results = phan_tich_cau_cheo(training_data[-7:])
    
    predict_rows = []
    for n in range(100):
        number_str = f"{n:02d}"

        freq_7days = sum(1 for d in previous_7_days if has_number_in_day(number_str, d))
        freq_prev_day = 1 if previous_7_days and has_number_in_day(number_str, previous_7_days[-1]) else 0

        is_ngang = 0
        cau_ngang_strength = 0
        for c in cau_ngang_results:
            if c.get("final") == number_str:
                is_ngang = 1
                cau_ngang_strength = len(c.get("history", []))
                break

        is_cheo = 0
        cau_cheo_strength = 0
        if isinstance(cau_cheo_results, dict):
            for cap_so, caus in cau_cheo_results.items():
                if cap_so == number_str:
                    is_cheo = 1
                    cau_cheo_strength = len(caus)
                    break
        else:
            for c in cau_cheo_results:
                if c.get("final") == number_str:
                    is_cheo = 1
                    cau_cheo_strength = len(c.get("history", []))
                    break
        
        in_any_cau = 1 if (is_ngang or is_cheo) else 0
        
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
            last_gap = gaps[-1] if gaps else len(previous_30_days)
            consecutive_count = sum(1 for g in gaps if g == 1)
        else:
            avg_gap = min_gap = max_gap = last_gap = len(previous_30_days)
            consecutive_count = 0
        days_since_last = (len(previous_30_days) - 1 - appearance_indices[-1]) if appearance_indices else len(previous_30_days)

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
            "current_date": current_date_for_prediction,  # Ngày cuối cùng có kết quả
            "next_date": predict_date,  # Ngày cần dự đoán
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

    # Fill NaN / types
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