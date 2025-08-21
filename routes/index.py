from flask import Blueprint, render_template, request, session, jsonify
from app.utils.crawl import (
    fetch_and_save_data,
    get_today_result,
    get_result_by_date,
    get_db,
    thong_ke_dau_duoi,
    get_past_5_results_with_stats,
    format_date_for_display
)
from datetime import datetime, timedelta, date
from bson import ObjectId

bp = Blueprint('main', __name__)

def get_week_day():
    today = datetime.today()
    db = get_db()
    start_of_week = today - timedelta(days=today.weekday())
    days = []
    available_dates = [r["date"] for r in db.kq_xs.find({}, {"date": 1})]
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        day_str = f"{day.day}-{day.month}-{day.year}"
        days.append({
            "label": f"T{i+2}" if i < 6 else "CN",
            "date_str": f"/{day_str}",
            "available": day_str in available_dates
        })
    return days

@bp.route('/')
def home():
    print("✅ Đã vào route /")
    fetch_and_save_data(date.today())
    result = get_today_result()
    week_days = get_week_day()
    user = session.get("user")

    db = get_db()
    # Lấy feed
    posts = list(db.feed.find({}).sort("time", -1))
    for p in posts:
        p["_id"] = str(p["_id"])
        if isinstance(p.get("time"), datetime):
            p["time"] = p["time"].strftime("%d-%m-%Y %H:%M:%S")
        # Format time for comments
        for c in p.get("comments", []):
            if isinstance(c.get("time"), datetime):
                c["time"] = c["time"].strftime("%d-%m-%Y %H:%M:%S")

    # Lấy thông báo cho user (like/comment/friend)
    notifications = []
    unseen_count = 0
    if user:
        user_id = str(user.get("_id", ""))
        if user_id:
            notifications = list(
                db.notifications.find({"user_id": user_id}).sort("time", -1)
            )
            for n in notifications:
                n["_id"] = str(n["_id"])
                if isinstance(n.get("time"), datetime):
                    n["time"] = n["time"].strftime("%d-%m-%Y %H:%M:%S")
                if not n.get("seen", False):
                    unseen_count += 1

    if not result:
        today = datetime.today()
        ngay = today.strftime("%d-%m-%Y")
        result = {
            "date": ngay,
            "ketqua": {"G1": [], "G2": [], "G3": [], "G4": [], "G5": [], "G6": [], "G7": [], "ĐB": []},
            "is_waiting": True
        }
    else:
        try:
            result["date"] = datetime.strptime(result["date"], "%d-%m-%Y").strftime("%d-%m-%Y")
        except:
            pass

    thong_ke = thong_ke_dau_duoi(result["ketqua"])
    past_results = get_past_5_results_with_stats(get_result_by_date, thong_ke_dau_duoi)

    return render_template(
        'index.html',
        result=result,
        week_days=week_days,
        user=user,
        thong_ke=thong_ke,
        past_results=past_results,
        posts=posts,
        notifications=notifications,
        unseen_count=unseen_count
    )

@bp.route("/ket-qua/<ngay>")
def ket_qua_ngay(ngay):
    user = session.get("user")
    db = get_db()
    # Lấy feed
    posts = list(db.feed.find({}).sort("time", -1))
    for p in posts:
        p["_id"] = str(p["_id"])
        if isinstance(p.get("time"), datetime):
            p["time"] = p["time"].strftime("%d-%m-%Y %H:%M:%S")
        # Format time for comments
        for c in p.get("comments", []):
            if isinstance(c.get("time"), datetime):
                c["time"] = c["time"].strftime("%d-%m-%Y %H:%M:%S")

    # Notifications (LUÔN lấy tất cả — cả seen & unseen)
    notifications = []
    unseen_count = 0
    if user:
        user_id = str(user.get("_id", ""))
        if user_id:
            notifications = list(
                db.notifications.find({"user_id": user_id}).sort("time", -1)
            )
            for n in notifications:
                n["_id"] = str(n["_id"])
                if isinstance(n.get("time"), datetime):
                    n["time"] = n["time"].strftime("%d-%m-%Y %H:%M:%S")
                if not n.get("seen", False):
                    unseen_count += 1

    result = get_result_by_date(ngay)
    week_days = get_week_day()
    past_results = get_past_5_results_with_stats(get_result_by_date, thong_ke_dau_duoi)

    if result:
        result["date"] = format_date_for_display(result["date"])
        thong_ke = thong_ke_dau_duoi(result["ketqua"])
    else:
        result = {
            "date": format_date_for_display(ngay),
            "ketqua": {"ĐB": [], "G1": [], "G2": [], "G3": [], "G4": [], "G5": [], "G6": [], "G7": []},
            "is_waiting": True
        }
        thong_ke = {str(i): [] for i in range(10)}

    return render_template(
        "index.html",
        result=result,
        week_days=week_days,
        user=user,
        thong_ke=thong_ke,
        past_results=past_results,
        posts=posts,
        notifications=notifications,
        unseen_count=unseen_count
    )

# ================== FEED API ==================
@bp.route("/feed/post", methods=["POST"])
def post_feed():
    db = get_db()
    user = session.get("user")
    if not user:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    data = request.get_json()
    content = data.get("content")
    if not content:
        return jsonify({"error": "Vui lòng nhập nội dung"}), 400

    post_id = db.feed.insert_one({
        "user_id": str(user["_id"]),
        "user_name": user["name"],
        "user_picture": user["picture"],
        "content": content,
        "likes": 0,
        "comments": [],
        "time": datetime.now()
    }).inserted_id

    post = db.feed.find_one({"_id": ObjectId(post_id)})
    post["_id"] = str(post["_id"])
    post["time"] = post["time"].strftime("%d-%m-%Y %H:%M:%S")
    return jsonify(post)

@bp.route("/feed/like/<post_id>", methods=["POST"])
def like_post(post_id):
    db = get_db()
    user = session.get("user")

    if not user:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    post = db.feed.find_one({"_id": ObjectId(post_id)})
    if not post:
        return jsonify({"error": "Bài viết không tồn tại"}), 404

    user_id = str(user["_id"])
    if "liked_by" not in post:
        post["liked_by"] = []

    # Nếu user đã like rồi → unlike (giảm 1 + gỡ user khỏi danh sách)
    if user_id in post["liked_by"]:
        result = db.feed.find_one_and_update(
            {"_id": ObjectId(post_id)},
            {
                "$inc": {"likes": -1},
                "$pull": {"liked_by": user_id}
            },
            return_document=True
        )
        return jsonify({"likes": result["likes"], "liked": False})

    # Nếu chưa like → like (tăng 1 + thêm user vào danh sách)
    result = db.feed.find_one_and_update(
        {"_id": ObjectId(post_id)},
        {
            "$inc": {"likes": 1},
            "$addToSet": {"liked_by": user_id}
        },
        return_document=True
    )

    # Thêm thông báo cho chủ bài (chỉ khi like, không thông báo lúc unlike)
    if str(user["_id"]) != str(result["user_id"]):
        db.notifications.insert_one({
            "user_id": str(result["user_id"]),
            "type": "like",
            "post_id": str(result["_id"]),
            "from_user": user["name"],
            "time": datetime.now(),
            "seen": False
        })

    return jsonify({"likes": result["likes"], "liked": True})


@bp.route("/feed/comment/<post_id>", methods=["POST"])
def comment_post(post_id):
    db = get_db()
    user = session.get("user")
    if not user:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    data = request.get_json()
    content = data.get("content")
    if not content:
        return jsonify({"error": "Vui lòng nhập nội dung bình luận"}), 400

    comment = {
        "user_name": user["name"],
        "user_picture": user["picture"],
        "content": content,
        "time": datetime.now()
    }

    result = db.feed.find_one_and_update(
        {"_id": ObjectId(post_id)},
        {"$push": {"comments": comment}},
        return_document=True
    )

    if not result:
        return jsonify({"error": "Bài viết không tồn tại"}), 404

    # Thêm thông báo cho chủ bài
    if str(user["_id"]) != str(result["user_id"]):
        db.notifications.insert_one({
            "user_id": str(result["user_id"]),
            "type": "comment",
            "post_id": str(result["_id"]),
            "from_user": user["name"],
            "time": datetime.now(),
            "seen": False
        })

    comment["time"] = comment["time"].strftime("%d-%m-%Y %H:%M:%S")
    return jsonify(comment)

# ================== MARK NOTIFICATIONS AS SEEN ==================
@bp.route("/notifications/seen/<notification_id>", methods=["POST"])
def mark_notification_seen(notification_id):
    db = get_db()
    user = session.get("user")
    if not user:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    result = db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": str(user["_id"])},
        {"$set": {"seen": True}}
    )
    if result.modified_count == 1:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Notification not found"})

# ================== FRIEND SYSTEM ==================
@bp.route("/friends/search", methods=["GET"])
def search_friends():
    """Tìm kiếm người dùng để kết bạn (theo tên, username)"""
    db = get_db()
    user = session.get("user")
    if not user:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"users": []})

    # Tìm user trùng tên, username (không trả về chính mình)
    results = list(db.users.find({
        "$and": [
            {"_id": {"$ne": ObjectId(user["_id"])}},
            {"$or": [{"name": {"$regex": q, "$options": "i"}},
                     {"username": {"$regex": q, "$options": "i"}}]}
        ]
    }, {"password": 0}))  # loại bỏ mật khẩu

    for u in results:
        u["_id"] = str(u["_id"])
    return jsonify({"users": results})


@bp.route("/friends/send_request/<friend_id>", methods=["POST"])
def send_friend_request(friend_id):
    """Gửi lời mời kết bạn"""
    db = get_db()
    user = session.get("user")
    if not user:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    # Kiểm tra đã là bạn chưa
    existing = db.friends.find_one({
        "$or": [
            {"user_id": str(user["_id"]), "friend_id": friend_id},
            {"user_id": friend_id, "friend_id": str(user["_id"])}
        ]
    })
    if existing:
        return jsonify({"error": "Đã là bạn bè"}), 400

    # Kiểm tra đã gửi lời mời chưa
    request_exist = db.friend_requests.find_one({
        "from_user": str(user["_id"]),
        "to_user": friend_id
    })
    if request_exist:
        return jsonify({"error": "Đã gửi lời mời trước đó"}), 400

    db.friend_requests.insert_one({
        "from_user": str(user["_id"]),
        "from_user_name": user["name"],       # 👈 thêm tên
        "from_user_picture": user["picture"], # 👈 thêm avatar nếu muốn
        "to_user": friend_id,
        "time": datetime.now()
    })

    # ✅ Tạo notification cho người nhận (lưu cả id + name)
    db.notifications.insert_one({
        "user_id": friend_id,
        "type": "friend_request",
        "from_user_id": str(user["_id"]),
        "from_user": user["name"],
        "time": datetime.now(),
        "seen": False
    })

    return jsonify({"ok": True})


@bp.route("/friends/requests", methods=["GET"])
def get_friend_requests():
    """Lấy danh sách lời mời đến"""
    db = get_db()
    user = session.get("user")
    if not user:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    requests = list(db.friend_requests.find({"to_user": str(user["_id"])}))
    for r in requests:
        r["_id"] = str(r["_id"])
        from_user = db.users.find_one({"_id": ObjectId(r["from_user"])}, {"password": 0})
        if from_user:
            from_user["_id"] = str(from_user["_id"])
            r["from_user_info"] = from_user
    return jsonify({"requests": requests})


@bp.route("/friends/respond_request/<request_id>", methods=["POST"])
def respond_friend_request(request_id):
    """Chấp nhận hoặc từ chối lời mời kết bạn"""
    db = get_db()
    user = session.get("user")
    if not user:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    data = request.get_json()
    action = data.get("action")  # accept / reject
    fr = db.friend_requests.find_one({"_id": ObjectId(request_id)})
    if not fr or fr["to_user"] != str(user["_id"]):
        return jsonify({"error": "Lời mời không tồn tại"}), 404

    from_user = fr["from_user"]
    to_user = fr["to_user"]

    if action == "accept":
        # Thêm vào danh sách bạn bè 2 chiều
        db.friends.insert_many([
            {"user_id": from_user, "friend_id": to_user, "time": datetime.now()},
            {"user_id": to_user, "friend_id": from_user, "time": datetime.now()}
        ])
        # Xóa request
        db.friend_requests.delete_one({"_id": ObjectId(request_id)})

        # Tạo notification cho người gửi
        db.notifications.insert_one({
            "user_id": from_user,
            "type": "friend_request_accepted",
            "from_user_id": str(user["_id"]),
            "from_user": user["name"],
            "time": datetime.now(),
            "seen": False
        })
        return jsonify({"ok": True, "message": "Đã chấp nhận lời mời"})

    elif action == "reject":
        db.friend_requests.delete_one({"_id": ObjectId(request_id)})
        return jsonify({"ok": True, "message": "Đã từ chối lời mời"})

    return jsonify({"error": "Action không hợp lệ"}), 400


@bp.route("/friends/list", methods=["GET"])
def list_friends():
    """Danh sách bạn bè"""
    db = get_db()
    user = session.get("user")
    if not user:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    friends = list(db.friends.find({"user_id": str(user["_id"])}))
    friend_ids = [f["friend_id"] for f in friends]
    friend_users = list(db.users.find({"_id": {"$in": [ObjectId(fid) for fid in friend_ids]}}, {"password": 0}))
    for f in friend_users:
        f["_id"] = str(f["_id"])
    return jsonify({"friends": friend_users})
