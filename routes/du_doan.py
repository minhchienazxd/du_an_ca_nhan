from flask import Blueprint, render_template, request, current_app, jsonify
from app.utils import phan_tich, du_doan_ml, du_doan_tt
import time

du_doan_bp = Blueprint('du_doan', __name__, url_prefix='/du_doan')

@du_doan_bp.route('/', methods=['GET', 'POST'])
def index():
    ket_qua_truyen_thong = None
    ket_qua_machine_learning = None
    thoi_gian_xu_ly = {}
    
    if request.method == 'POST':
        collection = current_app.db["kq_xs"]
        
        # Kiểu dự đoán
        kieu_du_doan = request.form.get('kieu_du_doan', 'truyen_thong')
        so_du_doan = int(request.form.get('so_du_doan', 10))
        
        if kieu_du_doan == 'truyen_thong':
            start_time = time.time()
            ket_qua_truyen_thong = du_doan_tt.du_doan_tt(
                collection, so_du_doan=so_du_doan
            )
            thoi_gian_xu_ly['truyen_thong'] = round(time.time() - start_time, 2)
            
        elif kieu_du_doan == 'machine_learning':
            start_time = time.time()
            ket_qua_machine_learning = du_doan_ml.du_doan_ml(
                collection, so_du_doan=so_du_doan
            )
            thoi_gian_xu_ly['machine_learning'] = round(time.time() - start_time, 2)
            
        elif kieu_du_doan == 'tat_ca':
            start_time = time.time()
            ket_qua_truyen_thong = du_doan_tt.du_doan_tt(
                collection, so_du_doan=so_du_doan
            )
            thoi_gian_xu_ly['truyen_thong'] = round(time.time() - start_time, 2)
            
            start_time = time.time()
            ket_qua_machine_learning = du_doan_ml.du_doan_ml(
                collection, so_du_doan=so_du_doan
            )
            thoi_gian_xu_ly['machine_learning'] = round(time.time() - start_time, 2)
    
    return render_template('du_doan.html', 
                         ket_qua_truyen_thong=ket_qua_truyen_thong,
                         ket_qua_machine_learning=ket_qua_machine_learning,
                         thoi_gian_xu_ly=thoi_gian_xu_ly)

@du_doan_bp.route('/api/du_doan', methods=['GET'])
def api_du_doan():
    collection = current_app.db["kq_xs"]
    kieu = request.args.get('kieu', 'truyen_thong')
    so_du_doan = int(request.args.get('so_du_doan', 10))
    
    if kieu == 'truyen_thong':
        ket_qua = du_doan_tt.du_doan_tt(collection, so_du_doan=so_du_doan)
    elif kieu == 'machine_learning':
        ket_qua = du_doan_ml.du_doan_ml(collection, so_du_doan=so_du_doan)
    else:
        return jsonify({"error": "Kiểu dự đoán không hợp lệ"})
    
    return jsonify(ket_qua)