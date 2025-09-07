from collections import Counter, defaultdict
from datetime import datetime
import numpy as np
from .phan_tich import (
    phan_tich_cham, phan_tich_tong_lo, phan_tich_lo_roi,
    phan_tich_cau_ngang, phan_tich_cau_cheo,
    phan_tich_theo_thu, phan_tich_lap_deu_chi_tiet,
    get_last_days, has_valid_ketqua, get_all_last_two_digits
)
import random

def du_doan_tt(collection, so_du_doan=10):
    """
    Hệ thống dự đoán XSMB - Phiên bản cải tiến
    - Kết quả ổn định khi chạy nhiều lần
    - Vẫn tính dữ liệu mới từ MongoDB
    """
    try:
        # Cố định seed cho tất cả các phần ngẫu nhiên
        random.seed(123)
        np.random.seed(123)

        # Lấy dữ liệu
        phan_tich_cham_result = phan_tich_cham(collection, so_ngay=7)
        phan_tich_tong_lo_result = phan_tich_tong_lo(collection)
        phan_tich_lo_roi_result = phan_tich_lo_roi(collection, so_ngay=100)
        phan_tich_cau_ngang_result = phan_tich_cau_ngang(collection, so_ngay=7)
        phan_tich_cau_cheo_result = phan_tich_cau_cheo(collection, so_ngay=7)
        phan_tich_theo_thu_result = phan_tich_theo_thu(collection, so_ngay=30)
        phan_tich_lap_deu_result = phan_tich_lap_deu_chi_tiet(collection, so_ngay=30)

        # Ngày tham chiếu cố định: ngày mới nhất trong dữ liệu
        data_30_ngay = get_last_days(collection, 30)
        if data_30_ngay:
            hom_nay_str = max(doc["date"] for doc in data_30_ngay)
            hom_nay = datetime.strptime(hom_nay_str, "%d-%m-%Y")
        else:
            hom_nay = datetime.now()

        diem_so = defaultdict(float)
        ly_do_so = defaultdict(list)

        # 1. Điểm từ phân tích chạm
        if phan_tich_cham_result:
            if "cham_all" in phan_tich_cham_result:
                cham_all = phan_tich_cham_result["cham_all"]
                total_count = sum(info["count"] for info in cham_all.values())
                for cham, info in sorted(cham_all.items()):
                    count = info.get("count", 0)
                    if total_count > 0 and count > 0:
                        ti_le = count / total_count
                        diem_cham_all = (1 - ti_le) * 5.0
                        for so in range(100):
                            so_str = f"{so:02d}"
                            if cham in so_str:
                                diem_so[so_str] += diem_cham_all
                                if diem_cham_all > 0:
                                    ly_do_so[so_str].append(
                                        f"Chạm {cham} (tỷ lệ thấp: {ti_le:.2%}) (+{diem_cham_all:.2f} điểm)"
                                    )
            if "cham_db" in phan_tich_cham_result:
                cham_db = phan_tich_cham_result["cham_db"]
                for cham, info in sorted(cham_db.items()):
                    count = info.get("count", 0)
                    dates = info.get("dates", [])
                    if count >= 2:
                        diem_cham_db = count * 1.5
                        for so in range(100):
                            so_str = f"{so:02d}"
                            if cham in so_str:
                                diem_so[so_str] += diem_cham_db
                                ly_do_so[so_str].append(
                                    f"Chạm ĐB {cham} ({count} lần: {', '.join(dates)}) (+{diem_cham_db:.2f} điểm)"
                                )

        # 2. Điểm từ tổng lô
        if phan_tich_tong_lo_result:
            recent_days = sorted(list(phan_tich_tong_lo_result.keys()))[-7:]
            tong_tan_suat = defaultdict(int)
            for ngay in recent_days:
                tong_data = phan_tich_tong_lo_result[ngay]
                for tong, count in tong_data.items():
                    tong_tan_suat[tong] += count
            total_tong_count = sum(tong_tan_suat.values())
            for tong, count in sorted(tong_tan_suat.items()):
                if total_tong_count > 0:
                    ti_le = count / total_tong_count
                    diem_tong = (1 - ti_le) * 4.0
                    for so in range(100):
                        so_str = f"{so:02d}"
                        if (int(so_str[0]) + int(so_str[1])) % 10 == int(tong):
                            diem_so[so_str] += diem_tong
                            if diem_tong > 0:
                                ly_do_so[so_str].append(
                                    f"Tổng {tong} (tỷ lệ thấp: {ti_le:.2%}) (+{diem_tong:.2f} điểm)"
                                )

        # 3. Điểm từ lô rơi
        if phan_tich_lo_roi_result:
            da_cong_diem_ngaymai = set()
            for key in ["db", "nhieu_nhay"]:
                if key in phan_tich_lo_roi_result:
                    xac_suat = phan_tich_lo_roi_result[key]["xac_suat"]
                    if xac_suat >= 70:
                        so_set = set()
                        for chi_tiet in phan_tich_lo_roi_result[key].get("chi_tiet", []):
                            parts = chi_tiet.split()
                            if len(parts) >= 2 and parts[1].isdigit():
                                so_set.add(parts[1])
                        for so in sorted(so_set):
                            diem_ngaymai = (xac_suat - 70) * 0.1
                            diem_so[so] += diem_ngaymai
                            ly_do_so[so].append(
                                f"Lô rơi từ {key} (XS ngày mai: {xac_suat}%) (+{diem_ngaymai:.2f} điểm)"
                            )
                            da_cong_diem_ngaymai.add(so)

            if "ung_vien" in phan_tich_lo_roi_result:
                for ung_vien in sorted(phan_tich_lo_roi_result["ung_vien"], key=lambda x: x.get("so", "00")):
                    so = ung_vien.get("so", "00")
                    ty_le = ung_vien.get("ty_le", 0)
                    if ty_le >= 30 and so not in da_cong_diem_ngaymai:
                        diem_ung_vien = (ty_le - 30) * 0.05
                        diem_so[so] += diem_ung_vien
                        ly_do_so[so].append(
                            f"Ứng viên lô rơi (tỷ lệ: {ty_le}%) (+{diem_ung_vien:.2f} điểm)"
                        )

        # 4. Điểm từ cầu ngang
        if phan_tich_cau_ngang_result:
            cau_theo_so = defaultdict(list)
            for cau in phan_tich_cau_ngang_result:
                so_final = cau.get("final", "00")
                so_reverse = cau.get("final_reverse", "00")
                cau_theo_so[so_final].append(cau)
                cau_theo_so[so_reverse].append(cau)
            for so, caus in sorted(cau_theo_so.items()):
                diem_cau_ngang = min(len(caus) * 1.5, 8.0)
                diem_so[so] += diem_cau_ngang
                if diem_cau_ngang > 0:
                    ly_do_so[so].append(f"Có {len(caus)} cầu ngang (+{diem_cau_ngang:.2f} điểm)")

        # 5. Điểm từ cầu chéo
        if phan_tich_cau_cheo_result:
            for so, caus in sorted(phan_tich_cau_cheo_result.items()):
                diem_cau_cheo = min(len(caus) * 1.2, 10.0)
                diem_so[so] += diem_cau_cheo
                if diem_cau_cheo > 0:
                    ly_do_so[so].append(f"Có {len(caus)} cầu chéo (+{diem_cau_cheo:.2f} điểm)")

        # 6. Điểm theo thứ
        if phan_tich_theo_thu_result:
            hom_nay = datetime.now().weekday()
            thu_labels = ["Thứ 2","Thứ 3","Thứ 4","Thứ 5","Thứ 6","Thứ 7","Chủ Nhật"]
            hom_nay_label = thu_labels[hom_nay]
            if hom_nay_label in phan_tich_theo_thu_result:
                top_3 = phan_tich_theo_thu_result[hom_nay_label].get("top_3", [])
                for item in top_3:
                    so_item = item.get("so", "00")
                    xac_suat = item.get("xac_suat", 0)
                    diem_theo_thu = xac_suat * 0.1
                    diem_so[so_item] += diem_theo_thu
                    if diem_theo_thu > 0:
                        ly_do_so[so_item].append(f" {hom_nay_label.capitalize()} (XS: {xac_suat}%) (+{diem_theo_thu:.2f} điểm)")

        # 7. Điểm từ số lặp đều
        if phan_tich_lap_deu_result:
            for so, data in sorted(phan_tich_lap_deu_result.items()):
                so_lan = data.get("so_lan", 0)
                patterns = data.get("patterns", [])
                ngay_gan_nhat = data.get("ngay_gan_nhat", "")
                diem_ngay_gan_nhat = 0
                if ngay_gan_nhat:
                    try:
                        ngay_gan_nhat_dt = datetime.strptime(ngay_gan_nhat, "%d-%m-%Y")
                        so_ngay_cach = (hom_nay - ngay_gan_nhat_dt).days
                        diem_ngay_gan_nhat = max(0, (30 - so_ngay_cach) * 0.2)
                    except:
                        pass
                diem_chu_ky = 0
                for pattern in patterns:
                    if pattern.get("do_chinh_xac", 0) >= 30:
                        diem_chu_ky += pattern.get("do_chinh_xac", 0) * 0.05
                diem_lap = min(diem_ngay_gan_nhat + diem_chu_ky, 6.0)
                diem_so[so] += diem_lap
                if diem_lap > 0:
                    ly_do = f"Chu kỳ"
                    if diem_ngay_gan_nhat > 0:
                        ly_do += f"gần đây ({ngay_gan_nhat}), "
                    if diem_chu_ky > 0:
                        chu_ky_info = [f" {p['chu_ky']} ngày ({p['do_chinh_xac']}%)" for p in patterns if p.get("do_chinh_xac",0)>=30]
                        ly_do += f"{', '.join(chu_ky_info)}, "
                    ly_do += f"(+{diem_lap:.2f} điểm)"
                    ly_do_so[so].append(ly_do)

        # 8. Điểm từ tần suất xuất hiện
        tan_suat = Counter()
        for doc in data_30_ngay:
            if has_valid_ketqua(doc):
                last_two_digits = get_all_last_two_digits(doc.get("ketqua", {}))
                tan_suat.update(set(last_two_digits))
        for so, count in sorted(tan_suat.items()):
            diem_tan_suat = (30 - count) * 0.3
            diem_so[so] += diem_tan_suat
            if diem_tan_suat > 0:
                ly_do_so[so].append(f"Ít xuất hiện ({count}/30 ngày) (+{diem_tan_suat:.2f} điểm)")

        # Sắp xếp theo điểm giảm dần
        so_xep_hang = sorted(diem_so.items(), key=lambda x: x[1], reverse=True)

        top_so = []
        for so, diem in so_xep_hang[:so_du_doan]:
            top_so.append({
                "so": so,
                "diem": round(diem, 2),
                "ly_do": ly_do_so.get(so, ["Không có thông tin chi tiết"]),
                "so_ly_do": len(ly_do_so.get(so, []))
            })

        return {
            "du_doan": top_so,
            "thong_ke": {
                "tong_so": len(diem_so),
                "diem_cao_nhat": round(so_xep_hang[0][1], 2) if so_xep_hang else 0,
                "diem_thap_nhat": round(so_xep_hang[-1][1], 2) if so_xep_hang else 0,
                "trung_binh_ly_do": round(np.mean([len(ly_do_so.get(so, [])) for so, _ in so_xep_hang[:so_du_doan]]), 1) if so_xep_hang else 0
            },
            "phan_tich": {
                "cham": phan_tich_cham_result,
                "tong_lo": phan_tich_tong_lo_result,
                "lo_roi": phan_tich_lo_roi_result,
                "cau_ngang": phan_tich_cau_ngang_result,
                "cau_cheo": phan_tich_cau_cheo_result,
                "theo_thu": phan_tich_theo_thu_result,
                "lap_deu": phan_tich_lap_deu_result
            }
        }

    except Exception as e:
        print(f"Lỗi trong dự đoán XSMB: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
