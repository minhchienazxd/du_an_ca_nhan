# routes/thong_ke.py
from flask import Blueprint, render_template, request
from app.utils.crawl import get_all_results, get_db 
from app.utils.phan_tich import thong_ke_cham_trong_ngay_moi_nhat, thong_ke_tong_lo, thong_ke_lo_roi, phan_tich_cau_ngang
from datetime import datetime

bp_thong_ke = Blueprint("thong_ke", __name__)

@bp_thong_ke.route("/thong-ke", methods=["GET"])
def thong_ke():
    db = get_db()
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    query = {}
    if from_date and to_date:
        from_obj = datetime.strptime(from_date, "%Y-%m-%d")
        to_obj = datetime.strptime(to_date, "%Y-%m-%d")

        from_str = f"{from_obj.day}-{from_obj.month}-{from_obj.year}"
        to_str = f"{to_obj.day}-{to_obj.month}-{to_obj.year}"
        query = {"date": {"$gte": from_str, "$lte": to_str}}
    data = list(db.kq_xs.find(query))
# Sort theo ngày thực (dd-mm-yyyy) thay vì sort theo chuỗi
    data.sort(key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"), reverse=True)

    thong_ke_data = []

    for item in data:
        row = {"date": item["date"], "counts": {}}
        all_numbers = []
        db_number = item["ketqua"].get("ĐB", [])
        for giai, so_list in item["ketqua"].items():
            all_numbers.extend(so_list)

        for so in all_numbers:
            if len(so) >= 2:
                last2 = so[-2:]
                row["counts"][last2] = row["counts"].get(last2, 0) + 1
        
        row["db"] = [s[-2:] for s in db_number if len(s) >= 2]
        thong_ke_data.append(row)
    return render_template("thong_ke.html", data=thong_ke_data)
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
    info = {}

    if request.method == "POST":
        action = request.form.get("action")

        # 1. Tần suất
    
            
        if action == "cham":
            try:
                cham_data = thong_ke_cham_trong_ngay_moi_nhat(collection)
            except Exception as e:
                print(f"Lỗi phân tích chạm: {e}")

        # 3. Tổng lô (tự lấy 30 ngày gần nhất)
        elif action == "tong_lo":
            try:
                tong_lo_data = thong_ke_tong_lo(collection)
            except Exception as e:
                print(f"Lỗi phân tích tổng lô: {e}")

        elif action == "lo_roi":
            try:
                lo_roi_data = thong_ke_lo_roi(collection)
            except Exception as e:
                print(f"Lỗi phân tích tổng lô: {e}")
        elif action == "cau_ngang":
            try:
                cau_ngang = phan_tich_cau_ngang(collection)
            except Exception as e:
                print(f"lỗi phân tích cầu ngang")


    return render_template(
        "phan_tich.html",
        action=action,
        cham_data=cham_data,
        tong_lo_data=tong_lo_data,
        lo_roi_data=lo_roi_data,
        cau_ngang=cau_ngang,
        info=info
    )
