from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from datetime import datetime
from bson import ObjectId
from app.utils.crawl import get_db

bp_lo_ghi = Blueprint("lo_ghi", __name__)

@bp_lo_ghi.route("/ghi-lo", methods=["GET", "POST"])
def ghi_lo():
    db = get_db()

    # Kiểm tra đăng nhập
    if "user" not in session:
        flash("Vui lòng đăng nhập để ghi lô", "error")
        return redirect(url_for("dang_nhap.dang_nhap"))

    user_id = session["user"].get("_id")
    if not user_id:
        flash("Không tìm thấy ID người dùng", "error")
        return redirect(url_for("dang_nhap.dang_nhap"))

    user_id = ObjectId(user_id)
    user = db.users.find_one({"_id": user_id})

    if not user:
        flash("Không tìm thấy thông tin người dùng", "error")
        return redirect(url_for("dang_nhap.dang_nhap"))

    if request.method == "POST":
        number = request.form.get("number", "").strip()
        diem = request.form.get("diem")
        loai = request.form.get("loai")

        # Validate số
        if not number.isdigit() or len(number) != 2:
            flash("Số không hợp lệ. Chỉ được nhập đúng 2 chữ số.", "error")
            return redirect(url_for("lo_ghi.ghi_lo"))

        # Validate loại
        if loai not in ["db", "loto"]:
            flash("Loại không hợp lệ", "error")
            return redirect(url_for("lo_ghi.ghi_lo"))

        # Validate điểm
        try:
            diem = int(diem)
            if diem <= 0:
                raise ValueError()
        except:
            flash("Điểm phải là số nguyên dương", "error")
            return redirect(url_for("lo_ghi.ghi_lo"))

        # Tính tiền cần trừ
        ty_gia = 1000 if loai == "db" else 24000
        tong_tien = diem * ty_gia
        so_du = user.get("balance", 0)

        if so_du < tong_tien:
            flash(f"Số dư không đủ. Cần {tong_tien:,} VND, bạn chỉ có {so_du:,} VND", "error")
            return redirect(url_for("lo_ghi.ghi_lo"))

        # Trừ tiền người dùng
        db.users.update_one({"_id": user_id}, {"$inc": {"balance": -tong_tien}})
        session["user"]["balance"] = so_du - tong_tien  # cập nhật lại session

        # Lưu lịch sử ghi lô
        if session.get("user"):
            email = session["user"]["email"]
            user_id = session["user"]["_id"]
            current_app.db["ghi_lo"].insert_one({
                "user_id": ObjectId(user_id),
                "email": email,
                "number": number,
                "diem": diem,
                "loai": loai,
                "tru_tien": tong_tien,
                "status": "pending",
                "time": datetime.utcnow()


            })
            

        flash("Ghi lô thành công. Tiền đã được trừ!", "success")
        return redirect(url_for("lo_ghi.ghi_lo"))

    # GET method: hiển thị form & lịch sử
    lich_su = list(db.lo_ghi.find({"user_id": user_id}).sort("created_at", -1))
    return render_template("ghi_lo.html", lich_su=lich_su, balance=user.get("balance", 0))
