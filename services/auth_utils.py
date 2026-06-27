"""Shared auth helpers."""
from functools import wraps
from flask import session, redirect, url_for, jsonify


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.signin_page"))
        return f(*args, **kwargs)
    return decorated


def login_required_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="authentication required"), 401
        return f(*args, **kwargs)
    return decorated