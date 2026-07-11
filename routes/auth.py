"""Auth routes — thin wrappers over Supabase Auth."""
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from services.supabase_client import get_supabase

auth_bp = Blueprint("auth", __name__)


# ── PAGE ROUTES ──
@auth_bp.get("/signin")
def signin_page():
    if "user_id" in session:
        return redirect(url_for("workspace"))
    return render_template("login.html")


@auth_bp.get("/signup")
def signup_page():
    if "user_id" in session:
        return redirect(url_for("workspace"))
    return render_template("signup.html")


# ── API ROUTES ──
@auth_bp.post("/signup")
def signup():
    data = request.get_json(force=True)
    email = data.get("email")
    password = data.get("password")
    full_name = data.get("full_name", "").strip()

    if not email or not password:
        return jsonify(error="email and password required"), 400

    if not full_name:
        return jsonify(error="full_name is required"), 400

    try:
        res = get_supabase().auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {"full_name": full_name}
            }
        })

        if res.user:
            session["user_id"] = res.user.id
            session.permanent = True
            session["email"] = res.user.email
            session["full_name"] = full_name

            try:
                from services.supabase_client import get_supabase_admin
                get_supabase_admin().table("profiles").upsert({
                    "id": res.user.id,
                    "email": email,
                    "full_name": full_name,
                }).execute()
            except Exception as profile_err:
                print(f"[ANA] profile save failed: {profile_err}")

        return jsonify(ok=True, user_id=res.user.id if res.user else None)

    except Exception as e:
        return jsonify(error=str(e)), 400


@auth_bp.post("/signin")
def signin():
    data = request.get_json(force=True)
    email, password = data.get("email"), data.get("password")
    try:
        res = get_supabase().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        session["user_id"] = res.user.id
        session.permanent = True
        session["email"] = res.user.email
        session["access_token"] = res.session.access_token

        try:
            from services.supabase_client import get_supabase_admin
            profile = get_supabase_admin().table("profiles").select("full_name").eq("id", res.user.id).single().execute()
            session["full_name"] = profile.data.get("full_name", "") if profile.data else ""
        except Exception as profile_err:
            print(f"[ANA] profile fetch on signin failed: {profile_err}")
            session["full_name"] = ""

        return jsonify(ok=True, user_id=res.user.id, email=res.user.email)
    except Exception as e:
        return jsonify(error=str(e)), 401


@auth_bp.post("/signout")
def signout():
    session.clear()
    return jsonify(ok=True)


@auth_bp.get("/signout")
def signout_get():
    session.clear()
    return redirect(url_for("landing"))


@auth_bp.get("/me")
def me():
    if "user_id" not in session:
        resp = jsonify(authenticated=False)
    else:
        resp = jsonify(
            authenticated=True,
            user_id=session["user_id"],
            email=session.get("email"),
        )
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@auth_bp.get("/forgot-password")
def forgot_password_page():
    return render_template("forgot_password.html")


@auth_bp.post("/forgot-password")
def forgot_password_post():
    data = request.get_json(force=True)
    email = data.get("email")
    if not email:
        return jsonify(error="Email required"), 400
    try:
        get_supabase().auth.reset_password_email(
            email,
            options={"redirect_to": "https://ana-vkl4.onrender.com/auth/reset-password"}
        )
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(error=str(e)), 400


@auth_bp.get("/reset-password")
def reset_password_page():
    return render_template("reset_password.html")


@auth_bp.post("/reset-password")
def reset_password():
    data = request.get_json(force=True)
    new_password = data.get("password")
    access_token = data.get("access_token")
    if not new_password or not access_token:
        return jsonify(error="Missing password or token"), 400
    try:
        client = get_supabase()
        client.auth.set_session(access_token, data.get("refresh_token", ""))
        client.auth.update_user({"password": new_password})
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(error=str(e)), 400