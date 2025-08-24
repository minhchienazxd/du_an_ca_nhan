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
    # fetch_and_save_data(date.today())  # BỎ HOẶC DI CHUYỂN RA ROUTE RIÊNG

    result = get_today_result()
    week_days = get_week_day()
    user = session.get("user")
    db = get_db()

    # ===== POSTS =====
    posts = list(db.feed.find().sort("time", -1))
    for p in posts:
        p["_id"] = str(p["_id"])
        p["time"] = p["time"].strftime("%d-%m-%Y %H:%M:%S")
        if "liked_by" not in p: p["liked_by"] = []
        if "comments" not in p: p["comments"] = []
        p["liked_by_current_user"] = session.get("user") and str(session["user"]["_id"]) in p["liked_by"]
    # ===== NOTIFICATIONS =====
    notifications = list(db.notifications.find().sort("time", -1))
    unseen_count = sum(1 for n in notifications if not n.get("seen", False))
    for n in notifications:
        n["_id"] = str(n["_id"])
        n["time"] = n["time"].strftime("%d-%m-%Y %H:%M:%S")

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

    def wrapper_get_today_result(_):
        return get_today_result()

    past_results = get_past_5_results_with_stats(wrapper_get_today_result, thong_ke_dau_duoi)

    return render_template(
        'index.html',
        result=result,
        week_days=week_days,
        user=user,
        thong_ke=thong_ke,
        past_results=past_results,
        notifications=notifications,
        unseen_count=unseen_count,
        posts=posts
    )


@bp.route("/ket-qua/<ngay>")
def ket_qua_ngay(ngay):
    user = session.get("user")

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
    )

# ================== FEED API ==================
