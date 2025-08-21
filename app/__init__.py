from flask import Flask 
from models.database import init_db
from routes import index, tk_pt, dang_nhap, nap_rut_ls, admin, ghi_lo
from app.utils.crawl import get_db
import os
def create_app():
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app = Flask(__name__)

    app.secret_key = os.getenv("FLASK_SECRET_KEY")
    init_db()
    app.db = get_db()
    for rule in app.url_map.iter_rules():
        print(rule.endpoint, rule)

    # Initialize the database
    
    # Additional app configuration can go here
    app.register_blueprint(index.bp)
    app.register_blueprint(tk_pt.bp_thong_ke)
    app.register_blueprint(dang_nhap.bp_dang_nhap)
    app.register_blueprint(dang_nhap.google_bp, url_prefix="/login")
    app.register_blueprint(nap_rut_ls.bp_nap_rut_ls)
    app.register_blueprint(admin.admin_bp)
    app.register_blueprint(ghi_lo.bp_lo_ghi)

    return app
