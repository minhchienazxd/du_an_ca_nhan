from flask import Blueprint, render_template, request, redirect, url_for, current_app, session
from bson import ObjectId
from datetime import datetime
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Trang quản lý ngân hàng
@admin_bp.route("/bank")
def manage_bank():
    banks = current_app.db["bank"].find()
    return render_template("bank.html", banks=banks)

@admin_bp.route("/bank/add", methods=["POST"])
def add_bank():
    bank_name = request.form.get("bank_name")
    account_number = request.form.get("account_number")
    account_name = request.form.get("account_name")

    current_app.db["bank"].insert_one({
        "bank_name": bank_name,
        "account_number": account_number,
        "account_name": account_name
    })
    return redirect(url_for("admin.manage_bank"))


@admin_bp.route("/bank/delete/<bank_id>")
def delete_bank(bank_id):
    from bson.objectid import ObjectId
    current_app.db["bank"].delete_one({"_id": ObjectId(bank_id)})
    return redirect(url_for("admin.manage_bank"))

@admin_bp.route("/users")
def manage_users():
    if not session.get("user") or session['user'].get('role') != 'admin':
        return redirect("/")

    users = list(current_app.db["users"].find())
    user_status_list = []

    for user in users:
        query = {
            "$or": [
                {"email": user.get("email", "")},
                {"phone": user.get("phone", "")}
            ]
        }

        # Đếm số lượng trạng thái pending
        pending_nap = current_app.db["nap_tien"].count_documents({
            **query,
            "status": "pending"
        })
        pending_rut = current_app.db["rut_tien"].count_documents({
            **query,
            "status": "pending"
        })
        pending_ghi_lo = current_app.db["ghi_lo"].count_documents({
            **query,
            "status": "pending"
        })

        user_status_list.append({
            "user": user,
            "pending_nap": pending_nap,
            "pending_rut": pending_rut,
            "pending_ghi_lo": pending_ghi_lo,
            "total_pending": pending_nap + pending_rut + pending_ghi_lo
        })

    return render_template("admin_users.html", user_status_list=user_status_list)


@admin_bp.route("/user/<user_id>",methods=["GET"], endpoint='user_detail')
def user_detail(user_id):
    user = current_app.db["users"].find_one({"_id": ObjectId(user_id)})
    if not user:
        return "Không tìm thấy người dùng", 404

    # Dùng email hoặc phone để tìm lịch sử
    query = {
        "$or": [
            {"email": user.get("email", "")},
            {"phone": user.get("phone", "")}
        ]
    }

    nap_tiens = list(current_app.db["nap_tien"].find(query).sort("time", -1))
    rut_tiens = list(current_app.db["rut_tien"].find(query).sort("time", -1))
    ghi_los = list(current_app.db["ghi_lo"].find(query).sort("date", -1))

    return render_template("admin_user_detail.html", 
        user=user,
        nap_tiens=nap_tiens,
        rut_tiens=rut_tiens,
        ghi_los=ghi_los,
        is_admin=True
    )
# Phên duyệt hoặc từ chối nạp tiền
# ✅ Xác nhận nạp tiền
@admin_bp.route("/xac_nhan_nap/<nap_id>", methods=["POST"])
def xac_nhan_nap(nap_id):
    nap = current_app.db["nap_tien"].find_one({"_id": ObjectId(nap_id)})
    if not nap:
        return "Không tìm thấy bản ghi nạp", 404

    user = current_app.db["users"].find_one({"_id": nap["user_id"]})
    if not user:
        return "Không tìm thấy người dùng", 404

    # Cập nhật trạng thái + cộng tiền
    current_app.db["nap_tien"].update_one(
        {"_id": ObjectId(nap_id)},
        {"$set": {"status": "Thành công"}}
    )
    current_app.db["users"].update_one(
        {"_id": user["_id"]},
        {"$inc": {"balance": int(nap.get("amount", 0))}}
    )

    return redirect(request.referrer or "/")

# ✅ Từ chối nạp tiền
@admin_bp.route("/tu_choi_nap/<nap_id>", methods=["POST"])
def tu_choi_nap(nap_id):
    current_app.db["nap_tien"].update_one(
        {"_id": ObjectId(nap_id)},
        {"$set": {"status": "Thất bại"}}
    )
    return redirect(request.referrer or "/")

# ✅ Xác nhận rút tiền
@admin_bp.route("/xac_nhan_rut/<rut_id>", methods=["POST"])
def xac_nhan_rut(rut_id):
    rut = current_app.db["rut_tien"].find_one({"_id": ObjectId(rut_id)})
    if not rut or rut["status"] != "pending":
        return "Yêu cầu không hợp lệ", 400

    user = current_app.db["users"].find_one({"_id": rut["user_id"]})
    if not user or user["balance"] < int(rut["amount"]):
        return "Không đủ tiền hoặc không tìm thấy người dùng", 400

    # Trừ tiền và cập nhật trạng thái
    current_app.db["users"].update_one(
        {"_id": user["_id"]},
        {"$inc": {"balance": -int(rut["amount"])}}
    )
    current_app.db["rut_tien"].update_one(
        {"_id": ObjectId(rut_id)},
        {"$set": {"status": "Thành công"}}
    )

    return redirect(request.referrer or "/")

# ✅ Từ chối rút tiền
@admin_bp.route("/tu_choi_rut/<rut_id>", methods=["POST"])
def tu_choi_rut(rut_id):
    current_app.db["rut_tien"].update_one(
        {"_id": ObjectId(rut_id)},
        {"$set": {"status": "Thất bại"}}
    )
    return redirect(request.referrer or "/")

@admin_bp.route("/admin/xu_ly_ghi_lo/<ghi_lo_id>", methods=["POST"])
def xu_ly_ghi_lo(ghi_lo_id):
    ket_qua = request.form.get("ket_qua")  # "thang" hoặc "thua"
    if ket_qua not in ["win", "lose"]:
        return "Kết quả không hợp lệ", 400

    ghi_lo = current_app.db["ghi_lo"].find_one({"_id": ObjectId(ghi_lo_id)})
    if not ghi_lo:
        return "Không tìm thấy ghi lô", 404

    if ghi_lo.get("status") != "pending":
        return "Ghi lô đã xử lý", 400

    user = current_app.db["users"].find_one({"_id": ObjectId(ghi_lo["user_id"])})
    if not user:
        return "Không tìm thấy người dùng", 404

    diem = int(ghi_lo.get("diem", 0))
    loai = ghi_lo.get("loai", "")

    # Tính tiền thắng
    so_tien_thang = 0
    if ket_qua == "win":
        if loai == "db":
            so_tien_thang = diem * 70000
        elif loai == "loto":
            so_tien_thang = diem * 80000

        # Cộng tiền vào tài khoản
        if so_tien_thang > 0:
            current_app.db["users"].update_one(
                {"_id": user["_id"]},
                {"$inc": {"balance": so_tien_thang}}
            )

    # Cập nhật trạng thái ghi lô
    current_app.db["ghi_lo"].update_one(
        {"_id": ObjectId(ghi_lo_id)},
        {"$set": {
            "status": "processed",
            "ket_qua": ket_qua,
            "so_tien_thang": so_tien_thang
        }}
    )

    return redirect(request.referrer or "/")