"""Misc API."""
import os
from flask import Blueprint, jsonify, session
from services.supabase_client import get_supabase_admin

api_bp = Blueprint("api", __name__)


def _require_user():
    return session.get("user_id")


@api_bp.get("/health")
def health():
    return jsonify(
        ok=True,
        service="ANA",
        tagline="Think. Learn. Assist.",
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    )


@api_bp.get("/models")
def models():
    return jsonify(
        recommended=[
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ]
    )


@api_bp.get("/profile")
def get_profile():
    user_id = _require_user()
    if not user_id:
        return jsonify(error="auth required"), 401
    try:
        sb = get_supabase_admin()
        row = sb.table("profiles").select("*").eq("id", user_id).single().execute()
        return jsonify(row.data or {})
    except Exception as e:
        return jsonify(error=str(e)), 400


@api_bp.post("/profile")
def update_profile():
    user_id = _require_user()
    if not user_id:
        return jsonify(error="auth required"), 401
    from flask import request
    data = request.get_json(force=True)
    full_name = data.get("full_name", "").strip()
    if not full_name:
        return jsonify(error="full_name required"), 400
    try:
        sb = get_supabase_admin()
        sb.table("profiles").upsert({
            "id": user_id,
            "full_name": full_name,
        }).execute()
        session["full_name"] = full_name
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(error=str(e)), 400


@api_bp.post("/change-password")
def change_password():
    user_id = _require_user()
    if not user_id:
        return jsonify(error="auth required"), 401
    from flask import request
    data = request.get_json(force=True)
    password = data.get("password", "").strip()
    if not password or len(password) < 6:
        return jsonify(error="password too short"), 400
    try:
        sb = get_supabase_admin()
        sb.auth.admin.update_user_by_id(user_id, {"password": password})
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(error=str(e)), 400





@api_bp.post("/delete-account")
def delete_account():
    user_id = _require_user()
    if not user_id:
        return jsonify(error="auth required"), 401
    try:
        sb = get_supabase_admin()
        # delete all user data
        sb.table("document_chunks").delete().eq("user_id", user_id).execute()
        sb.table("documents").delete().eq("user_id", user_id).execute()
        convos = sb.table("conversations").select("id").eq("user_id", user_id).execute()
        convo_ids = [c["id"] for c in (convos.data or [])]
        for cid in convo_ids:
            sb.table("messages").delete().eq("conversation_id", cid).execute()
        sb.table("conversations").delete().eq("user_id", user_id).execute()
        sb.table("profiles").delete().eq("id", user_id).execute()
        sb.auth.admin.delete_user(user_id)
        session.clear()
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(error=str(e)), 400