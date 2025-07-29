from flask import Blueprint, jsonify, render_template, request
from vidwiz.shared.utils import jwt_required
from vidwiz.shared.models import Video, Note
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta, timezone
from flask import current_app, redirect, url_for, make_response
from vidwiz.shared.models import User, db

core_bp = Blueprint("core", __name__)


@core_bp.route("/", methods=["GET"])
def index():
    return render_template("landing.html")


@core_bp.route("/dashboard", methods=["GET"])
def get_dashboard_page():
    return render_template("dashboard.html")


@core_bp.route("/dashboard/<video_id>", methods=["GET"])
@jwt_required
def get_video_page(video_id):
    return render_template("video.html")


@core_bp.route("/search", methods=["GET"])
@jwt_required
def get_search_results():
    query = request.args.get("query", None)
    if query is None:
        return jsonify({"error": "Query parameter is required"}), 400
    # Only include videos that have at least one note, and belong to the current user
    videos = (
        Video.query
        .filter(Video.title.ilike(f"%{query}%"), Video.user_id == request.user_id)
        .join(Note, Video.video_id == Note.video_id)
        .group_by(Video.id)
        .order_by(Video.created_at.desc())
        .all()
    )
    if not videos:
        return jsonify({"error": "No videos found matching the query"}), 404
    all_videos = [
        {"video_id": video.video_id, "video_title": video.title} for video in videos
    ]
    return jsonify(all_videos), 200


@core_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            return render_template("signup.html", error="Username and password required.")
        if User.query.filter_by(username=username).first():
            return render_template("signup.html", error="Username already exists.")
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("core.login"))
    return render_template("signup.html")

@core_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Username and password required."}), 400
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Invalid username or password."}), 401
        token = jwt.encode({
            "user_id": user.id,
            "username": user.username,
            "exp": datetime.now(timezone.utc) + timedelta(hours=24)
        }, current_app.config["SECRET_KEY"], algorithm="HS256")
        return jsonify({"token": token})
    return render_template("login.html")

@core_bp.route("/logout", methods=["GET"])
def logout():
    resp = make_response(redirect(url_for("core.login")))
    resp.set_cookie("jwt_token", "", expires=0)
    return resp
