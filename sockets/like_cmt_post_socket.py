# like_cmt_post_rocket.py
from flask_socketio import emit
from datetime import datetime
from bson import ObjectId
from app.utils.crawl import get_db  # function để lấy db MongoDB
from flask_socketio import join_room, leave_room

def register_feed_events(socketio):
    @socketio.on("connect")
    def on_connect():
        emit("connected", {"ok": True})
    # ================= NOTIFICATION =================
    @socketio.on("join_user_room")
    def on_join_user_room(data):
        """User join room của chính mình để nhận thông báo"""
        user_id = data.get("user_id")
        if user_id:
            join_room(str(user_id))
            print(f"User {user_id} joined notification room")

    @socketio.on("send_notification")
    def on_send_notification(data):
        """
        data = {
            "type": "like|comment|friend_request|friend_accept",
            "post_id": "...",  # optional
            "content": "...",  # optional for comment
            "to_user_id": "...",  # QUAN TRỌNG: chỉ gửi đến user này
            "from_user_id": "...",
            "from_user_name": "...",
            "from_user_picture": "..."
        }
        """
        db = get_db()
        
        # KIỂM TRA: Không gửi thông báo cho chính mình
        if data.get("to_user_id") == data.get("from_user_id"):
            print("Bỏ qua thông báo gửi cho chính mình")
            return
        
        # KIỂM TRA: Đảm bảo có user nhận
        if not data.get("to_user_id"):
            print("Không có user nhận thông báo")
            return
        
        # Lưu thông báo vào database
        notification_data = {
            "type": data.get("type"),
            "post_id": data.get("post_id"),
            "content": data.get("content", ""),
            "to_user_id": data.get("to_user_id"),
            "from_user_id": data.get("from_user_id"),
            "from_user_name": data.get("from_user_name"),
            "from_user_picture": data.get("from_user_picture"),
            "seen": False,
            "time": datetime.utcnow()
        }
        
        notification_id = db.notifications.insert_one(notification_data).inserted_id
        
        # Gửi thông báo realtime đến user nhận
        notification = db.notifications.find_one({"_id": notification_id})
        if notification:
            # Chuyển đổi định dạng
            notification["_id"] = str(notification["_id"])
            notification["time"] = notification["time"].strftime("%d-%m-%Y %H:%M:%S")
            
            # QUAN TRỌNG: Chỉ gửi đến room của user nhận
            emit("new_notification", notification, room=str(data.get("to_user_id")))
            print(f"Đã gửi thông báo đến user {data.get('to_user_id')}")
    @socketio.on("mark_notification_seen")
    def on_mark_notification_seen(data):
        """
        data = {
            "notification_id": "..."
        }
        """
        db = get_db()
        notification_id = data.get("notification_id")
        
        if not notification_id:
            return emit("error", {"error": "MISSING_NOTIFICATION_ID"})
        
        # Đánh dấu thông báo đã xem
        db.notifications.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"seen": True}}
        )
        
        emit("notification_seen", {"success": True})
    
    # ================= POST FEED =================
    @socketio.on("post_feed")
    def on_post_feed(data):
        """
        data = {
            "user_id": "...",
            "user_name": "...",
            "user_picture": "...",
            "content": "..."
        }
        """
        db = get_db()

        user_id = data.get("user_id")
        user_name = data.get("user_name")
        user_picture = data.get("user_picture")
        content = (data.get("content") or "").strip()

        if not user_id or not user_name or not user_picture:
            return emit("error", {"error": "UNAUTHENTICATED"})
        if not content:
            return emit("error", {"error": "EMPTY_CONTENT"})

        # insert bài viết mới
        post_id = db.feed.insert_one({
            "user_id": str(user_id),
            "user_name": user_name,
            "user_picture": user_picture,
            "content": content,
            "likes": 0,
            "liked_by": [],
            "comments": [],
            "time": datetime.utcnow()
        }).inserted_id

        post = db.feed.find_one({"_id": ObjectId(post_id)})
        if post:
            post["_id"] = str(post["_id"])
            post["time"] = post["time"].strftime("%d-%m-%Y %H:%M:%S")

            # broadcast realtime cho tất cả client
            emit("new_post", post, broadcast=True)

    # ================= LIKE / UNLIKE POST =================
    @socketio.on("like_post")
    def on_like_post(data):
        """
        data = {
            "user_id": "...",
            "post_id": "..."
        }
        """
        db = get_db()
        user_id = data.get("user_id")
        post_id = data.get("post_id")

        if not user_id:
            return emit("error", {"error": "UNAUTHENTICATED"})
        if not post_id:
            return emit("error", {"error": "MISSING_POST_ID"})

        post = db.feed.find_one({"_id": ObjectId(post_id)})
        if not post:
            return emit("error", {"error": "POST_NOT_FOUND"})

        if str(user_id) in post.get("liked_by", []):
            # unlike
            result = db.feed.find_one_and_update(
                {"_id": ObjectId(post_id)},
                {"$inc": {"likes": -1}, "$pull": {"liked_by": str(user_id)}},
                return_document=True
            )
            liked = False
        else:
            # like
            result = db.feed.find_one_and_update(
                {"_id": ObjectId(post_id)},
                {"$inc": {"likes": 1}, "$addToSet": {"liked_by": str(user_id)}},
                return_document=True
            )
            liked = True
        if liked and post["user_id"] != user_id:
            from_user = db.users.find_one({"_id": ObjectId(user_id)})
            if from_user:
                # Gửi thông báo đến chủ bài viết
                socketio.emit("send_notification", {
                    "type": "like",
                    "post_id": post_id,
                    "to_user_id": post["user_id"],  # chủ bài viết
                    "from_user_id": user_id,        # người like
                    "from_user_name": from_user.get("name", "Unknown"),
                    "from_user_picture": from_user.get("picture", "")
                })

        if result:
            emit("update_like", {
                "post_id": post_id,
                "likes": result["likes"],
                "user_id": user_id,
                "liked": liked
            }, broadcast=True)

    # ================= COMMENT POST =================
    @socketio.on("comment_post")
    def on_comment_post(data):
        """
        data = {
            "user_id": "...",
            "user_name": "...",
            "user_picture": "...",
            "post_id": "...",
            "content": "..."
        }
        """
        db = get_db()

        user_id = data.get("user_id")
        user_name = data.get("user_name")
        user_picture = data.get("user_picture")
        post_id = data.get("post_id")
        content = (data.get("content") or "").strip()

        if not user_id or not user_name or not user_picture:
            return emit("error", {"error": "UNAUTHENTICATED"})
        if not post_id or not content:
            return emit("error", {"error": "INVALID"})

        comment = {
            "user_id": str(user_id),
            "user_name": user_name,
            "user_picture": user_picture,
            "content": content,
            "time": datetime.utcnow()
        }

        result = db.feed.find_one_and_update(
            {"_id": ObjectId(post_id)},
            {"$push": {"comments": comment}},
            return_document=True
        )

        if not result:
            return emit("error", {"error": "POST_NOT_FOUND"})

        comment["time"] = comment["time"].strftime("%d-%m-%Y %H:%M:%S")
        emit("new_comment", {"post_id": post_id, "comment": comment}, broadcast=True)
        # GỬI THÔNG BÁO COMMENT - CHỈ KHI KHÔNG PHẢI CHỦ POST
        if result["user_id"] != user_id:
            socketio.emit("send_notification", {
                "type": "comment",
                "post_id": post_id,
                "content": content,
                "to_user_id": result["user_id"],  # chủ bài viết
                "from_user_id": user_id,          # người comment
                "from_user_name": user_name,
                "from_user_picture": user_picture
            })
    @socketio.on("like_comment")
    def on_like_comment(data):
        """
        data = {
            "user_id": "...",
            "post_id": "...",
            "comment_id": "..."
        }
        """
        db = get_db()
        user_id = data.get("user_id")
        post_id = data.get("post_id")
        comment_id = data.get("comment_id")

        if not user_id:
            return emit("error", {"error": "UNAUTHENTICATED"})
        if not post_id or not comment_id:
            return emit("error", {"error": "MISSING_DATA"})

        post = db.feed.find_one({"_id": ObjectId(post_id)})
        if not post:
            return emit("error", {"error": "POST_NOT_FOUND"})

        # Tìm comment cụ thể
        comment_index = None
        for idx, comment in enumerate(post.get("comments", [])):
            if str(comment.get("_id", "")) == comment_id:
                comment_index = idx
                break

        if comment_index is None:
            return emit("error", {"error": "COMMENT_NOT_FOUND"})

        # Cập nhật like cho comment
        comment = post["comments"][comment_index]
        liked_by = comment.get("liked_by", [])
        
        if str(user_id) in liked_by:
            # Unlike comment
            new_likes = comment.get("likes", 0) - 1
            new_liked_by = [uid for uid in liked_by if uid != str(user_id)]
            liked = False
        else:
            # Like comment
            new_likes = comment.get("likes", 0) + 1
            new_liked_by = liked_by + [str(user_id)]
            liked = True

        # Cập nhật trong database
        update_query = {
            f"comments.{comment_index}.likes": new_likes,
            f"comments.{comment_index}.liked_by": new_liked_by
        }
        
        result = db.feed.find_one_and_update(
            {"_id": ObjectId(post_id)},
            {"$set": update_query},
            return_document=True
        )

        emit("update_comment_like", {
            "post_id": post_id,
            "comment_id": comment_id,
            "likes": new_likes,
            "liked": liked,
            "user_id": user_id
        }, broadcast=True)

    # ================= REPLY COMMENT =================
    @socketio.on("reply_comment")
    def on_reply_comment(data):
        """
        data = {
            "user_id": "...",
            "user_name": "...",
            "user_picture": "...",
            "post_id": "...",
            "comment_id": "...",
            "content": "..."
        }
        """
        db = get_db()

        user_id = data.get("user_id")
        user_name = data.get("user_name")
        user_picture = data.get("user_picture")
        post_id = data.get("post_id")
        comment_id = data.get("comment_id")
        content = (data.get("content") or "").strip()

        if not user_id or not user_name or not user_picture:
            return emit("error", {"error": "UNAUTHENTICATED"})
        if not post_id or not comment_id or not content:
            return emit("error", {"error": "INVALID"})

        # Tạo reply
        reply = {
            "_id": ObjectId(),
            "user_id": str(user_id),
            "user_name": user_name,
            "user_picture": user_picture,
            "content": content,
            "time": datetime.utcnow()
        }

        # Tìm comment và thêm reply
        result = db.feed.find_one_and_update(
            {"_id": ObjectId(post_id), "comments._id": ObjectId(comment_id)},
            {"$push": {"comments.$.replies": reply}},
            return_document=True
        )

        if not result:
            return emit("error", {"error": "POST_OR_COMMENT_NOT_FOUND"})

        reply["time"] = reply["time"].strftime("%d-%m-%Y %H:%M:%S")
        reply["_id"] = str(reply["_id"])
        
        emit("new_reply", {
            "post_id": post_id,
            "comment_id": comment_id,
            "reply": reply
        }, broadcast=True)
