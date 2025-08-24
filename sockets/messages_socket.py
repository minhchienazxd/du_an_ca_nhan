# app/sockets/friends.py

from datetime import datetime
from bson import ObjectId
from flask import session, request
from flask_socketio import emit, join_room
from app.utils.crawl import get_db


def room_for(a, b) -> str:
    """Tạo tên phòng cố định cho 1 cặp user."""
    return ":".join(sorted([str(a), str(b)]))


def is_friend(db, me: str, peer: str) -> bool:
    """Kiểm tra quan hệ bạn bè một chiều (me đã có peer trong bảng friends)."""
    return db.friends.find_one({"user_id": me, "friend_id": peer}) is not None


def save_message(db, sender_id: str, receiver_id: str, content: str) -> dict:
    """Lưu tin nhắn và trả payload đồng bộ với client."""
    now = datetime.utcnow()
    msg = {
        "sender_id": str(sender_id),
        "receiver_id": str(receiver_id),
        "content": content,
        "timestamp": now,
        "seen": False,
    }
    result = db.messages.insert_one(msg)
    return {
        "_id": str(result.inserted_id),
        "sender_id": str(sender_id),
        "receiver_id": str(receiver_id),
        "content": content,
        "timestamp": now.isoformat(),
        "seen": False,
    }


def _require_user():
    """Lấy user từ session; nếu không có trả None."""
    user = session.get("user")
    if not user:
        return None, None
    db = get_db()
    me = str(user["_id"])
    return db, me


def register_friend_events(socketio):
    """Đăng ký tất cả socket events (không lồng trong on_connect)."""

    @socketio.on("connect")
    def on_connect():
        # Chỉ thông báo đã kết nối; KHÔNG đăng ký handler ở đây.
        emit("connected", {"ok": True})

    # ============== FRIENDS ==============

    @socketio.on("get_friends")
    def on_get_friends():
        db, me = _require_user()
        if not me:
            return
        friends = list(db.friends.find({"user_id": me}))
        friend_list = []
        for f in friends:
            u = db.users.find_one({"_id": ObjectId(f["friend_id"])})
            if u:
                friend_list.append({
                    "_id": str(u["_id"]),
                    "name": u.get("name"),
                    "username": u.get("username"),
                    "picture": u.get("picture"),
                })
        emit("friends_list", friend_list)
    @socketio.on("send_friend_request")
    def on_send_friend_request(data):
        db, me = _require_user()
        if not me:
            return emit("error", {"error": "UNAUTHORIZED"})

        to_id = str(data.get("to_user_id"))
        if not to_id or to_id == me:
            return emit("error", {"error": "INVALID_ID"})

        # Kiểm tra user tồn tại
        if not db.users.find_one({"_id": ObjectId(to_id)}):
            return emit("error", {"error": "USER_NOT_FOUND"})

        # Kiểm tra đã gửi request trước đó chưa
        if db.friend_requests.find_one({"from_user_id": me, "to_user_id": to_id}):
            return emit("error", {"error": "ALREADY_REQUESTED"})

        # Kiểm tra đã là bạn bè chưa
        if is_friend(db, me, to_id):
            return emit("error", {"error": "ALREADY_FRIENDS"})

        db.friend_requests.insert_one({
            "from_user_id": me,
            "to_user_id": to_id,
            "time": datetime.utcnow(),
        })

        emit("friend_request_sent", {"from_user_id": me, "to_user_id": to_id}, broadcast=True, include_self=True)

    @socketio.on("get_friend_requests")
    def on_get_friend_requests():
        db, me = _require_user()
        if not me:
            return
        requests = list(db.friend_requests.find({"to_user_id": me}))
        req_list = []
        for r in requests:
            from_u = db.users.find_one({"_id": ObjectId(r["from_user_id"])})
            if from_u:
                req_list.append({
                    "_id": str(r["_id"]),
                    "from_user_id": str(from_u["_id"]),
                    "from_user_name": from_u.get("name"),
                    "from_user_picture": from_u.get("picture"),
                    "time": r["time"].strftime("%d-%m-%Y %H:%M:%S") if isinstance(r.get("time"), datetime) else str(r.get("time")),
                })
        emit("friend_requests_list", req_list)

    @socketio.on("accept_friend")
    def accept_friend(data):
        db, me = _require_user()
        if not me:
            return
        from_id = str(data.get("from_user_id"))
        if not from_id:
            return
        # Thêm bạn hai chiều
        db.friends.insert_one({"user_id": me, "friend_id": from_id})
        db.friends.insert_one({"user_id": from_id, "friend_id": me})
        # Xóa yêu cầu
        db.friend_requests.delete_one({"from_user_id": from_id, "to_user_id": me})
        emit("friend_added", {"friend_id": from_id}, room=request.sid)
    @socketio.on("reject_friend")
    def reject_friend(data):
        db, me = _require_user()
        if not me:
            return
        from_id = str(data.get("from_user_id"))
        if not from_id:
            return
        db.friend_requests.delete_one({"from_user_id": from_id, "to_user_id": me})
        emit("friend_rejected", {"from_user_id": from_id}, room=request.sid)
    @socketio.on("remove_friend")
    def remove_friend(data):
        db, me = _require_user()
        if not me:
            return
        friend_id = str(data.get("friend_id"))
        if not friend_id:
            return
        db.friends.delete_many({
            "$or": [
                {"user_id": me, "friend_id": friend_id},
                {"user_id": friend_id, "friend_id": me},
            ]
        })
        emit("friend_removed", {"friend_id": friend_id}, room=request.sid)

    @socketio.on("search_users")
    def search_users(data):
        db, me = _require_user()
        if not me:
            return emit("search_results", [])
        keyword = (data.get("keyword") or "").strip()
        if not keyword:
            return emit("search_results", [])
        users = list(db.users.find({
            "$or": [
                {"name": {"$regex": keyword, "$options": "i"}},
                {"username": {"$regex": keyword, "$options": "i"}},
            ],
            "_id": {"$ne": ObjectId(me)}
        }).limit(20))
        results = [{
            "_id": str(u["_id"]),
            "name": u.get("name"),
            "username": u.get("username"),
            "picture": u.get("picture"),
        } for u in users]
        emit("search_results", results)

    # ============== MESSAGES ==============

    @socketio.on("join")
    def on_join(data):
        db, me = _require_user()
        if not me:
            return emit("error", {"error": "UNAUTHORIZED"})
        peer_id = str(data.get("peer_id"))
        if not peer_id or not is_friend(db, me, peer_id):
            return emit("error", {"error": "NOT_FRIEND"})

        room = room_for(me, peer_id)
        join_room(room)

        msgs = list(db.messages.find({
            "$or": [
                {"sender_id": me, "receiver_id": peer_id},
                {"sender_id": peer_id, "receiver_id": me},
            ]
        }).sort("timestamp", -1).limit(50))
        msgs.reverse()

        history = [{
            "_id": str(m["_id"]),
            "sender_id": m["sender_id"],
            "receiver_id": m["receiver_id"],
            "content": m["content"],
            "timestamp": m["timestamp"].isoformat() if isinstance(m.get("timestamp"), datetime) else str(m.get("timestamp")),
            "seen": m.get("seen", False),
        } for m in msgs]

        emit("joined", {"room": room, "history": history})

    @socketio.on("send_message")
    def on_send_message(data):
        db, me = _require_user()
        if not me:
            return emit("error", {"error": "UNAUTHORIZED"})
        peer_id = str(data.get("peer_id"))
        content = (data.get("content") or "").strip()
        if not content or not peer_id or not is_friend(db, me, peer_id):
            return emit("error", {"error": "INVALID"})

        payload = save_message(db, me, peer_id, content)
        room = room_for(me, peer_id)
        emit("message", payload, room=room)

    @socketio.on("mark_seen")
    def on_mark_seen(data):
        db, me = _require_user()
        if not me:
            return
        peer_id = str(data.get("peer_id"))
        if not peer_id:
            return
        db.messages.update_many(
            {"sender_id": peer_id, "receiver_id": me, "seen": False},
            {"$set": {"seen": True}},
        )
        seen_msgs = db.messages.find(
            {"sender_id": peer_id, "receiver_id": me, "seen": True}
        ).sort("timestamp", -1).limit(50)
        seen_ids = [str(m["_id"]) for m in seen_msgs]
        room = room_for(me, peer_id)
        emit("seen_ack", {"peer_id": peer_id, "seen_ids": seen_ids}, room=room)

    @socketio.on("typing")
    def on_typing(data):
        db, me = _require_user()
        if not me:
            return
        peer_id = str(data.get("peer_id"))
        if not peer_id:
            return
        room = room_for(me, peer_id)
        emit(
            "typing",
            {"from": me, "typing": bool(data.get("typing"))},
            room=room,
            include_self=False,
        )
