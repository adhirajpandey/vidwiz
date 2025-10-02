import os
from flask import Blueprint, send_from_directory, current_app

frontend_bp = Blueprint("frontend", __name__)


@frontend_bp.route("/", defaults={"path": ""})
@frontend_bp.route("/<path:path>")
def catch_all(path):
    """
    Serve React app for all frontend routes.
    If the path matches a file inside dist (like assets), serve it.
    Otherwise, return index.html for React Router.
    """
    # The static folder for the app is configured to be 'dist'
    static_folder = current_app.static_folder

    # If a path is given and it exists as a file in the static folder, serve it
    if path and os.path.exists(os.path.join(static_folder, path)):
        return send_from_directory(static_folder, path)

    # Otherwise, serve the index.html for the React app
    return send_from_directory(static_folder, "index.html")
