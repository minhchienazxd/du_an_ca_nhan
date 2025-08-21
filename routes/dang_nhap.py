from flask import Blueprint, redirect, url_for, render_template, session, current_app, request
from flask_dance.contrib.google import make_google_blueprint, google
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.security import check_password_hash

load_dotenv()
import os

bp_dang_nhap = Blueprint("dang_nhap", __name__)

google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
    redirect_to="dang_nhap.google_login",
    scope=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"]
)
bp_dang_nhap.register_blueprint(google_bp, url_prefix="/login")

@bp_dang_nhap.route("/dang-nhap", methods=["GET", "POST"])
def show_login_page():
    if request.method == "POST":
        identifier = request.form.get("phone")  # dùng cho cả phone/email
        password = request.form.get("password")

        user = current_app.db["user"].find_one({"phone": identifier, "password": password})
        if user:
            session["user"] = {
                "name": user.get("name"),
                "email": user.get("email"),
                "picture": user.get("picture", ""),
                "method": "Phone",
                "balance": user.get("balance", 0),
                "role": "user"
            }
            return redirect(url_for("main.home"))

        # Nếu không phải user thì kiểm tra admin
        admin = current_app.db["admins"].find_one({
            "$or": [{"phone": identifier}, {"email": identifier}]
        })
        if admin and check_password_hash(admin["password"], password):
            session["user"] = {
                "name": admin.get("name"),
                "email": admin.get("email"),
                "role": "admin"
            }
            return redirect(url_for("main.home"))

        # Không tìm thấy ai cả
        return render_template("dang_nhap.html", error="Sai thông tin đăng nhập.")

    return render_template("dang_nhap.html")

@bp_dang_nhap.route("/dang-ky", methods=["GET", "POST"])
def dang_ky():
    if request.method == "POST":
        phone = request.form.get("phone")
        name = request.form.get("name")
        password = request.form.get("password")
        if current_app.db["users"].find_one({"phone": phone}):
            error = "Số điện thoại đã được sử dụng."
            return render_template("dang-ky.html", error=error)
        current_app.db["users"].insert_one({
            "name": name,
            "phone": phone,
            "password": password,
            "balance": 0,
            "method": "Phone",
            "login_time": datetime.utcnow()
        })
        return redirect(url_for("dang_nhap.show_login_page"))
    
    return render_template("dang_ky.html")


@bp_dang_nhap.route("/quen-mat-khau", methods=["GET", "POST"])
def quen_mat_khau():
    return "Trang quên mật khẩu đang được xây dựng."

@bp_dang_nhap.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return f"Lỗi khi đăng nhập: {resp.text}"
    
    user_info = resp.json()
    email = user_info.get("email")
    name = user_info.get("name")
    picture = user_info.get("picture")

    db = current_app.db["users"]

    # Kiểm tra người dùng có tồn tại không
    existing_user = db.find_one({"email": email})

    if existing_user:
        balance = existing_user.get("balance", 0)
        user_id = str(existing_user["_id"])  # 👈 Lấy _id từ DB
    else:
        # Nếu chưa có, tạo mới và lấy _id
        new_user = {
            "name": name,
            "email": email,
            "picture": picture,
            "method": "Google",
            "login_time": datetime.utcnow(),
            "balance": 0
        }
        result = db.insert_one(new_user)
        user_id = str(result.inserted_id)
        balance = 0

    # Nếu user đã có thì vẫn cập nhật lại một số thông tin
    db.update_one(
        {"email": email},
        {
            "$set": {
                "name": name,
                "picture": picture,
                "method": "Google",
                "login_time": datetime.utcnow()
            }
        }
    )

    # ✅ Lưu vào session đầy đủ
    session["user"] = {
        "_id": user_id,  # 👈 THÊM VÀO
        "name": name,
        "email": email,
        "picture": picture,
        "method": "Google",
        "balance": balance
    }

    return redirect(url_for("main.home"))
  # Chuyển về trang chính
@bp_dang_nhap.route("/logout", endpoint="logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("main.home"))  # hoặc trang nào bạn muốn về


