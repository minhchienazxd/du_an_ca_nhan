

from app import create_app, socketio
from models.database import init_db
from app.utils.crawl import fetch_and_save_data, auto_update  # file crawl bạn đang viết
import threading


app = create_app()
def start_background_task():
    init_db()
    fetch_and_save_data()  # crawl 1 lần khi start server
    t = threading.Thread(target=auto_update, daemon=True)
    t.start()
if __name__ == "__main__":
    host = "0.0.0.0"
    port = 5000
    print(f"\n 🚀 Server running at:")
    print(f"   ➜ Local:   http://127.0.0.1:{port}")
    print(f"   ➜ Network: http://{host}:{port}\n")
    start_background_task()
    socketio.run(app, host=host, port=port, debug=True)
