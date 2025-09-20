
from app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 5000
    print(f"\n 🚀 Server running at:")
    print(f"   ➜ Local:   http://127.0.0.1:{port}")
    print(f"   ➜ Network: http://{host}:{port}\n")
    socketio.run(app, host=host, port=port, debug=True)
