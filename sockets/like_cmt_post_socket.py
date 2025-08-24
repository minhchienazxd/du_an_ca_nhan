# like_cmt_post_rocket.py
from flask_socketio import emit
from datetime import datetime
from bson import ObjectId
from app.utils.crawl import get_db  # function để lấy db MongoDB


def register_feed_events(socketio):
    @socketio.on("connect")
    def on_connect():
        emit("connected", {"ok": True})

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

        emit("update_like", {
            "post_id": post_id,
            "likes": result["likes"],
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
