from flask import Flask
from models.database import init_db
from routes import index, tk_pt, dang_nhap, nap_rut_ls, admin, ghi_lo, du_doan
from app.utils.crawl import get_db
from flask_socketio import SocketIO
from sockets.like_cmt_post_socket import register_feed_events
from sockets.messages_socket import register_friend_events
import os

# Khởi tạo SocketIO global
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="eventlet",
    manage_session=True
)

def create_app():
    # Cho phép OAuth2 chạy trên HTTP (chỉ dev, không nên để production)
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    app = Flask(__name__)

    # SECRET_KEY dùng chung cho Flask session + SocketIO
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "default-secret-key")

    # Khởi tạo socketio với app
    socketio.init_app(app)

    # Khởi tạo DB
    init_db()
    app.db = get_db()

    # Debug: in ra tất cả routes đã đăng ký
    for rule in app.url_map.iter_rules():
        print(rule.endpoint, rule)

    # Đăng ký blueprint
    app.register_blueprint(index.bp)
    app.register_blueprint(tk_pt.bp_thong_ke)
    app.register_blueprint(dang_nhap.bp_dang_nhap)
    app.register_blueprint(dang_nhap.google_bp, url_prefix="/login")
    app.register_blueprint(nap_rut_ls.bp_nap_rut_ls)
    app.register_blueprint(admin.admin_bp)
    app.register_blueprint(ghi_lo.bp_lo_ghi)
    app.register_blueprint(du_doan.du_doan_bp)
    register_feed_events(socketio)
    register_friend_events(socketio)
    return app
