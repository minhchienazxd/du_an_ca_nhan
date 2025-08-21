from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from datetime import datetime
from flask import jsonify
from bson import ObjectId

bp_nap_rut_ls = Blueprint("nap_rut_ls", __name__)

@bp_nap_rut_ls.route("/nap-tien", methods=["GET", "POST"])
def nap_tien():
    if request.method == "POST":
        method = request.form.get("method")
        bank = request.form.get("bank")
        name = request.form.get("name")
        stk = request.form.get("stk")
        content = request.form.get("content")
        amount = int(request.form.get("amount"))

        if session.get("user"):
            email = session["user"]["email"]
            user_id = session["user"]["_id"]

            current_app.db["nap_tien"].insert_one({
                "user_id": ObjectId(user_id),
                "email": email,
                "method": method,
                "bank": bank,
                "name": name,
                "stk": stk,
                "content": content,
                "amount": amount,
                "status": "pending",
                "time": datetime.utcnow()
            })
            return jsonify({"message": "Yêu cầu nạp tiền đã được gửi!"})
        else:
            return jsonify({"message": "❌ Bạn chưa đăng nhập."}), 401


    # GET request
    return render_template("nap_tien.html")

@bp_nap_rut_ls.route("/api/bank-info")
def get_bank_info():
    bank = request.args.get("bank")
    bank_info = current_app.db["bank"].find_one({"bank_name": bank})

    if not bank_info:
        return {
            "account_name": None,
            "account_number": None
        }
    return {
        "account_name": bank_info.get("account_name"),
        "account_number": bank_info.get("account_number")
    }
@bp_nap_rut_ls.route("/rut-tien", methods=["GET", "POST"])
def rut_tien():
    if request.method == "POST":
        method = request.form.get("method")
        bank = request.form.get("bank")
        name = request.form.get("name")
        stk = request.form.get("stk")
        content = request.form.get("content")
        amount = int(request.form.get("amount"))

        # Ghi yêu cầu vào collection rut_tien
        if session.get("user"):
            email = session["user"]["email"]
            user_id = session["user"]["_id"]
            current_app.db["rut_tien"].insert_one({
                "user_id": ObjectId(user_id),
                "email": email,
                "method": method,
                "bank": bank,
                "name": name,
                "stk": stk,
                "content": content,
                "amount": amount,
                "status": "pending",
                "time": datetime.utcnow()
            })
            return jsonify({"message": "Yêu cầu rút tiền đã được gửi!"})
        else:
            return jsonify({"message": "❌ Bạn chưa đăng nhập."}), 401
    banks = list(current_app.db["bank"].find()) # Ví dụ: báo "yêu cầu đang chờ duyệt"
    return render_template("rut_tien_form.html", banks=banks)


@bp_nap_rut_ls.route("/lich-su")
def lich_su_giao_dich():
    if not session.get("user"):
        return redirect(url_for("dang_nhap.show_login_page"))
    
    user_id = ObjectId(session["user"]["_id"])
    nap_tiens = list(current_app.db["nap_tien"].find({"user_id": user_id}).sort("time", -1))
    rut_tiens = list(current_app.db["rut_tien"].find({"user_id": user_id}).sort("time", -1))
    ghi_los = list(current_app.db["ghi_lo"].find({"user_id": user_id}).sort("time", -1))

    return render_template(

        "admin_user_detail.html",
        user=session.get("user"),
        nap_tiens=nap_tiens,
        rut_tiens=rut_tiens,
        ghi_los=ghi_los,
        is_admin=False
    )