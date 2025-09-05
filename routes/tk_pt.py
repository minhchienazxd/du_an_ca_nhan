# routes/thong_ke.py
from flask import Blueprint, render_template, request
from app.utils.crawl import  get_db 
from datetime import datetime
from app.utils.phan_tich import phan_tich_cham, phan_tich_cau_cheo, phan_tich_cau_ngang, phan_tich_lap_deu_chi_tiet, phan_tich_lo_roi, phan_tich_theo_thu, phan_tich_tong_lo

bp_thong_ke = Blueprint("thong_ke", __name__)

@bp_thong_ke.route("/thong-ke", methods=["GET"])
def thong_ke():
    db = get_db()
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    # B1: lấy tất cả dữ liệu
    data = list(db.kq_xs.find({}))

    # B2: sort theo datetime thực
    data.sort(key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"), reverse=True)

    # B3: nếu có from/to thì lọc
    if from_date and to_date:
        from_obj = datetime.strptime(from_date, "%Y-%m-%d")
        to_obj = datetime.strptime(to_date, "%Y-%m-%d")
        data = [
            d for d in data
            if from_obj <= datetime.strptime(d["date"], "%d-%m-%Y") <= to_obj
        ]

    thong_ke_data = []
    for item in data:
        row = {"date": item["date"], "counts": {}}
        all_numbers = []

        # Lấy kết quả
        db_number = item["ketqua"].get("ĐB", [])
        for giai, so_list in item["ketqua"].items():
            all_numbers.extend(so_list)

        # Đếm tần suất
        for so in all_numbers:
            if len(so) >= 2:
                last2 = so[-2:]
                row["counts"][last2] = row["counts"].get(last2, 0) + 1

        row["db"] = [s[-2:] for s in db_number if len(s) >= 2]
        thong_ke_data.append(row)

    return render_template(
        "thong_ke.html",
        data=thong_ke_data,
        from_iso=from_date,
        to_iso=to_date
    )

def render_table(data):
    if not data: return "<p>Không có dữ liệu</p>"
    html = "<table><tr><th>Số</th><th>Tần suất</th></tr>"
    for so, dem in data:
        html += f"<tr><td>{so}</td><td>{dem}</td></tr>"
    html += "</table>"
    return html
@bp_thong_ke.route("/phan-tich", methods=["GET", "POST"])
def phan_tich():
    db = get_db()
    collection = db["kq_xs"]

    # Dữ liệu trả về
    action = None
    cham_data = None
    tong_lo_data = None
    lo_roi_data = None
    cau_ngang = None 
    cau_cheo_data = None
    phan_tich_thu_data = None
    lap_deu_data = None
    info = {}

    if request.method == "POST":
        action = request.form.get("action")
        cau_ngang = []

        # 1. Tần suất
    
            
        if action == "cham":
            try:
                cham_data = phan_tich_cham(collection)
            except Exception as e:
                print(f"Lỗi phân tích chạm: {e}")

        # 3. Tổng lô (tự lấy 30 ngày gần nhất)
        elif action == "tong_lo":
            try:
                tong_lo_data = phan_tich_tong_lo(collection)
            except Exception as e:
                print(f"Lỗi phân tích tổng lô: {e}")

        elif action == "lo_roi":
            try:
                lo_roi_data = phan_tich_lo_roi(collection)
            except Exception as e:
                print(f"Lỗi phân tích tổng lô: {e}")
        elif action == "cau_ngang":
            try:
                cau_ngang = phan_tich_cau_ngang(collection, so_ngay=7)
            except Exception as e:
                print(f"lỗi phân tích cầu ngang")
        elif action == "cau_cheo":
            try:
                cau_cheo_data = phan_tich_cau_cheo(collection)
            # Nhóm theo số nếu cần
            # grouped_cau_cheo = group_cau_by_number(cau_cheo_data)
            except Exception as e:
                print(f"Lỗi phân tích cầu chéo: {e}")
                cau_cheo_data = []
        elif action == "phan_tich_thu":
            try:
                phan_tich_thu_data = phan_tich_theo_thu(collection, so_ngay=30)
            except Exception as e:
                print(f"Lỗi phân tích theo thứ: {e}")
                phan_tich_thu_data = {}
        elif action == "lap_deu":
            try:
                lap_deu_data = phan_tich_lap_deu_chi_tiet(collection, so_ngay=30)
            except Exception as e:
                print(f"Lỗi phân tích lặp đều: {e}")
                lap_deu_data = {}

    return render_template(
        "phan_tich.html",
        action=action,
        cham_data=cham_data,
        tong_lo_data=tong_lo_data,
        lo_roi_data=lo_roi_data,
        cau_ngang=cau_ngang,
        cau_cheo_data=cau_cheo_data,
        phan_tich_thu_data=phan_tich_thu_data,
        lap_deu_data=lap_deu_data,
        info=info
    )
@bp_thong_ke.route("/cau-cheo/<cap_so>")
def chi_tiet_cau_cheo(cap_so):
    db = get_db()
    collection = db["kq_xs"]
    
    cau_cheo_data = phan_tich_cau_cheo(collection)
    cau_list = cau_cheo_data.get(cap_so, [])
    
    return render_template(
        "chi_tiet_cau_cheo.html",
        cap_so=cap_so,
        cap_so_dao=cap_so[1] + cap_so[0],
        cau_list=cau_list
    )