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
from datetime import datetime, timedelta

bp = Blueprint('main', __name__)

# ================= CONTEXT PROCESSOR CHUNG =================
@bp.app_context_processor
def inject_common_data():
    db = get_db()
    user = session.get("user")

    # FEED
    posts = list(db.feed.find().sort("time", -1))
    for p in posts:
        p["_id"] = str(p["_id"])
        p["time"] = p["time"].strftime("%d-%m-%Y %H:%M:%S")
        if "liked_by" not in p: p["liked_by"] = []
        if "comments" not in p: p["comments"] = []
        p["liked_by_current_user"] = str(user.get("_id")) in p["liked_by"] if user else False

    # NOTIFICATIONS
    notifications = list(db.notifications.find().sort("time", -1))
    unseen_count = sum(1 for n in notifications if not n.get("seen", False))
    for n in notifications:
        n["_id"] = str(n["_id"])
        n["time"] = n["time"].strftime("%d-%m-%Y %H:%M:%S")

    return dict(posts=posts, notifications=notifications, unseen_count=unseen_count, user=user)


# ================= HÀM HỖ TRỢ =================
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


# ================= ROUTES =================
@bp.route('/')
def home():
    db = get_db()

    # Crawl hôm nay nếu chưa có
    today_str = datetime.today().strftime("%d-%m-%Y")
    if not db.kq_xs.find_one({"date": today_str}):
        try:
            fetch_and_save_data()
        except Exception as e:
            print("❌ Lỗi khi crawl dữ liệu:", e)

    # Kết quả hôm nay
    result = get_today_result()
    week_days = get_week_day()

    if not result:
        result = {
            "date": today_str,
            "ketqua": {"ĐB": [], "G1": [], "G2": [], "G3": [], "G4": [], "G5": [], "G6": [], "G7": []},
            "is_waiting": True
        }
        thong_ke = {str(i): [] for i in range(10)}
    else:
        try:
            result["date"] = datetime.strptime(result["date"], "%d-%m-%Y").strftime("%d-%m-%Y")
        except:
            pass
        thong_ke = thong_ke_dau_duoi(result["ketqua"])

    # Lấy 5 kết quả trước với thống kê
    past_results = get_past_5_results_with_stats(get_result_by_date, thong_ke_dau_duoi, exclude_date=result.get("date"))

    return render_template(
        'index.html',
        result=result,
        week_days=week_days,
        thong_ke=thong_ke,
        past_results=past_results
    )


@bp.route("/ket-qua/<ngay>")
def ket_qua_ngay(ngay):
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
        thong_ke=thong_ke,
        past_results=past_results
    )

@bp.route('/api/notifications')
def get_notifications():
    if 'user' not in session or "_id" not in session['user']:
        return jsonify([])
    
    db = get_db()
    user_id = session['user']['_id']
    
    notifications = list(db.notifications.find(
        {"to_user_id": user_id}
    ).sort("time", -1).limit(50))
    
    # Chuyển đổi ObjectId thành string
    for notification in notifications:
        notification["_id"] = str(notification["_id"])
        if isinstance(notification.get("time"), datetime):
            notification["time"] = notification["time"].strftime("%d-%m-%Y %H:%M:%S")
    
    return jsonify(notifications)