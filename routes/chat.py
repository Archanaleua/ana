"""Chat routes — Groq inference + Supabase persistence."""
from flask import Blueprint, request, jsonify, session, render_template, Response, stream_with_context
from services.groq_client import chat as groq_chat, stream_chat
from services.supabase_client import get_supabase_admin
from services.auth_utils import login_required_api
import json

chat_bp = Blueprint("chat", __name__)


def _require_user():
    return session.get("user_id")


def _detect_language(text: str) -> str:
    import re

    if re.search(r'[\u0A80-\u0AFF]', text): return "Gujarati"
    if re.search(r'[\u0900-\u097F]', text): return "Hindi"
    if re.search(r'[\u0600-\u06FF]', text): return "Arabic"
    if re.search(r'[\u0980-\u09FF]', text): return "Bengali"
    if re.search(r'[\u0B80-\u0BFF]', text): return "Tamil"
    if re.search(r'[\u0C00-\u0C7F]', text): return "Telugu"
    if re.search(r'[\u0C80-\u0CFF]', text): return "Kannada"
    if re.search(r'[\u0D00-\u0D7F]', text): return "Malayalam"
    if re.search(r'[\u0A00-\u0A7F]', text): return "Punjabi"
    if re.search(r'[\u0400-\u04FF]', text): return "Russian"
    if re.search(r'[\u4E00-\u9FFF]', text): return "Chinese"
    if re.search(r'[\u3040-\u30FF]', text): return "Japanese"
    if re.search(r'[\uAC00-\uD7AF]', text): return "Korean"
    if re.search(r'[\u0370-\u03FF]', text): return "Greek"
    if re.search(r'[\u0590-\u05FF]', text): return "Hebrew"
    if re.search(r'[\u0E00-\u0E7F]', text): return "Thai"
    if re.search(r'[\u1200-\u137F]', text): return "Amharic"

    words = set(text.lower().split())

    strong_hindi = {
        "yaar", "kya", "bhai", "mujhe", "nahi", "mera", "tera",
        "haan", "chahiye", "bahut", "zyada", "abhi", "lekin",
        "raha", "rahi", "tum", "hota", "batao", "kaise", "kaisa",
        "phir", "woh", "yeh", "aur", "main", "dost", "ghar",
        "kese", "kese ho", "kaisa", "theek", "bilkul", "shukriya",
        "dhanyawad", "namaste", "samjha", "pata",
        "tha", "thi", "hain", "mere", "teri",
        "uska", "unka", "kyun", "kab", "kahan", "kitna", "bohot",
    }

    strong_gujarati = {
        "kem", "cho", "chhe", "nathi", "tamaru", "tamaro",
        "tamari", "aavjo", "olakho", "ghanu", "thodu", "saru",
        "maja", "bau", "javu", "avu", "tame",
        "shu", "su", "hatu", "hati", "hata",
        "karo", "kari", "karu", "karjo", "karva",
        "nai", "pan", "pachi",
        "kyare", "kyathi", "kyan", "kevu", "kevi",
        "maro", "mari", "mara", "taro", "tari", "tara",
        "avjo", "jaav", "jaavo", "ben",
        "gamtu", "gamti",
        "aayu", "gayu", "gai", "avyu", "avvi",
        "boljo", "sambhlo", "juo",
        "saras", "majama", "mazama",
        "tamne", "tane", "eni", "ena", "ame",
        "hoy", "hoi",
    }

    if words & strong_hindi and not words & strong_gujarati:
        return "Hindi"
    if words & strong_gujarati and not words & strong_hindi:
        return "Gujarati"

    hindi_score = len(words & strong_hindi)
    gujarati_score = len(words & strong_gujarati)
    if hindi_score > gujarati_score:
        return "Hindi"
    if gujarati_score > hindi_score:
        return "Gujarati"

    common_english = {
        "the", "is", "are", "was", "were", "what", "how", "why",
        "when", "where", "who", "which", "this", "that", "these",
        "those", "my", "your", "his", "her", "we", "they", "it",
        "can", "will", "do", "does", "did", "have", "has", "had",
        "summarize", "explain", "tell", "show", "give", "make",
        "help", "please", "thanks", "hello", "hi", "hey",
        "about", "from", "with", "into", "through", "and", "or",
        "but", "not", "all", "any", "some", "more", "also",
        "just", "like", "get", "use", "see", "know", "think",
        "want", "need", "good", "great", "best", "new", "first",
        "uploaded", "document", "file", "pdf", "chat", "message",
        "find", "search", "look", "check", "list", "count",
        "many", "much", "between", "days", "today", "yesterday",
        "date", "year", "month", "left", "remaining", "balance",
        "employee", "employees", "attendance", "leave", "leaves",
        "present", "absent", "department", "city", "salary",
        "on", "in", "at", "for", "of", "to", "by", "an", "a",
        "name", "id", "info", "details", "record", "records",
        "delete", "add", "update", "modify", "change",
    }
    if words & common_english:
        return "English"

    import difflib
    for w in words:
        if len(w) < 3:
            continue
        close_matches = difflib.get_close_matches(w, common_english, n=1, cutoff=0.75)
        if close_matches:
            return "English"

    from services.groq_client import _client
    try:
        resp = _client().chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{
                "role": "user",
                "content": (
                    f"Detect the language of this text. "
                    f"Reply with ONLY the language name in English, nothing else. "
                    f"If you are not confident, or the text could be a name, ID, or short command, "
                    f"reply 'English'. "
                    f"Examples: English, French, Spanish, German, Italian, "
                    f"Portuguese, Dutch, Turkish, Indonesian, Vietnamese, "
                    f"Malay, Swahili, Polish, Czech, Romanian, Hungarian, "
                    f"Finnish, Swedish, Norwegian, Danish, etc.\n\n"
                    f"Text: {text[:150]}"
                )
            }],
            temperature=0,
            max_tokens=10,
        )
        lang = resp.choices[0].message.content.strip()
        lang = lang.split('\n')[0].split('.')[0].strip()
        return lang if lang else "English"
    except Exception:
        return "English"


def _resolve_language_for_followup_reply(history: list[dict], user_msg: str) -> str | None:
    """
    Handles short replies that answer a PREVIOUS assistant question, where the
    reply itself (a bare city name, a bare person's name, etc.) is too short
    and ambiguous to reliably language-detect on its own — and where a wrong
    guess would silently derail an in-progress HR lookup or identity flow.

    This function ONLY affects which [LANG:XX] tag gets attached to the
    message. It never touches employee data, never calls any tool, and never
    changes what the message text actually says — it purely fixes a language-
    detection edge case for two specific, narrow situations:

    1. EMPLOYEE DISAMBIGUATION FOLLOW-UP
       Assistant just asked "which one did you mean?" after finding multiple
       employees with the same name. The user's short reply (a city,
       department, or "the first one") is resolving THAT ambiguity — it is
       not a language switch. We reuse the language of the ORIGINAL question
       that started this disambiguation, so the whole exchange stays
       consistent in whatever language the user was actually using.

    2. NAME REQUEST FOLLOW-UP
       Assistant just asked "what should I call you?" (e.g. after 'who am I'
       with no name on file). The user's reply is just their name — a bare
       name is unreliable to detect (can get misread as an Indian language
       purely because it sounds like one). Default this case to English,
       since it's identity/UI text, not an HR data query.

    Returns a language string if either case applies, else None — meaning
    the caller should fall back to normal _detect_language() as usual.
    """
    if not history or len(user_msg.split()) > 4:
        return None

    last = history[-1]
    if last.get("role") != "assistant":
        return None

    last_content = last.get("content", "").lower()

    # Case 1 — employee disambiguation follow-up
    disambiguation_markers = ["which one did you mean", "did you mean", "clarify"]
    if any(p in last_content for p in disambiguation_markers):
        for msg in reversed(history[:-1]):
            if msg.get("role") == "user":
                return _detect_language(msg.get("content", ""))
        return "English"  # no earlier user message found — safe fallback

    # Case 2 — name request follow-up
    name_request_markers = [
        "what should i call you",
        "what would you like me to call you",
        "don't know your name",
    ]
    if any(p in last_content for p in name_request_markers):
        return "English"

    return None

def _maybe_save_name_from_reply(sb, user_id: str, history: list[dict], user_msg: str) -> str | None:
    """
    If the assistant's last message asked the user for their name, treat this
    reply as their name, save it PERMANENTLY to profiles.full_name in the
    database (not just this session), and return it so the current turn can
    use it immediately too — without needing another round trip.

    This is a one-time save: once profiles.full_name is set, this function's
    trigger condition (assistant just asked for a name) won't fire again in
    future conversations, because the "who am I" flow will already have the
    real name and never ask again.

    Returns the name that was saved, or None if this isn't a name-reply case.
    """
    if not history or len(user_msg.split()) > 3:
        return None

    last = history[-1]
    if last.get("role") != "assistant":
        return None

    name_request_markers = [
        "what should i call you",
        "what would you like me to call you",
        "don't know your name",
    ]
    if not any(p in last.get("content", "").lower() for p in name_request_markers):
        return None

    name = user_msg.strip().title()
    if not name or len(name) > 60:
        return None

    try:
        sb.table("profiles").upsert({
            "id": user_id,
            "full_name": name,
        }).execute()
        session["full_name"] = name
        print(f"[ANA] Saved name '{name}' permanently for user {user_id}")
        return name
    except Exception as e:
        print(f"[ANA] Failed to save name: {e}")
        return None

def _load_context(sb, user_id: str, user_msg: str, document_id: str | None) -> str | None:
    try:
        query = sb.table("document_chunks").select("content").eq("user_id", user_id)
        if document_id:
            query = query.eq("document_id", document_id)
        chunks = query.limit(500).execute()
        chunk_contents = [c["content"] for c in (chunks.data or [])]

        if not document_id or not chunk_contents:
            return None

        from services.rag import top_k

        summarize_keywords = [
            "summarize", "summarise", "summerize", "summerise",
            "summary", "overview", "what is this", "what does this say",
            "explain this document", "explain this", "explain",
            "tell me about this", "what is in this", "describe",
            "describe this document", "give me summary", "give summary",
            "document summary", "what is document", "document me batao",
            "document vise", "this document", "this pdf", "this file",
            "read this", "check this", "analyse this", "analyze this",
            "what does it say", "what is it about", "tell me about it",
            "samjao", "samjav", "explain karo", "batao"
        ]

        if any(kw in user_msg.lower() for kw in summarize_keywords) or len(user_msg.split()) <= 4:
            relevant = chunk_contents[:10]
        else:
            relevant = top_k(user_msg, chunk_contents, k=10)

        if relevant:
            return "\n---\n".join(relevant)

    except Exception:
        pass
    return None


def _stream_and_persist(sb, conversation_id, user_id, user_msg, document_id):
    """Shared generator: builds context, streams the reply, saves both messages after."""
    msgs = (
        sb.table("messages")
        .select("role,content")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .limit(20)
        .execute()
    )
    history = (msgs.data or [])[-6:]

    saved_name = _maybe_save_name_from_reply(sb, user_id, history, user_msg)
    user_name = saved_name or session.get("full_name") or None

    context = _load_context(sb, user_id, user_msg, document_id)
    lang = _resolve_language_for_followup_reply(history, user_msg) or _detect_language(user_msg)
    user_msg_with_hint = f"[LANG:{lang}] {user_msg}"
    messages = history + [{"role": "user", "content": user_msg_with_hint}]

    full_reply = ""
    try:
        for token in stream_chat(messages, context=context, user_name=user_name):
            full_reply += token
            yield f"data: {json.dumps({'token': token})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return

    try:
        result = sb.table("messages").insert([
            {"conversation_id": conversation_id, "role": "user", "content": user_msg},
            {"conversation_id": conversation_id, "role": "assistant", "content": full_reply},
        ]).execute()

        user_message_id = result.data[0]["id"] if result.data else None

        yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id, 'grounded': bool(context), 'user_message_id': user_message_id})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@chat_bp.post("/send")
@login_required_api
def send():
    data = request.get_json(force=True)
    user_msg = (data.get("message") or "").strip()
    conversation_id = data.get("conversation_id")
    document_id = data.get("document_id")

    if not user_msg:
        return jsonify(error="message required"), 400

    user_id = _require_user()
    sb = get_supabase_admin()

    if not conversation_id:
        row = sb.table("conversations").insert(
            {"user_id": user_id, "title": user_msg[:60]}
        ).execute()
        conversation_id = row.data[0]["id"]

    return Response(
        stream_with_context(_stream_and_persist(sb, conversation_id, user_id, user_msg, document_id)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
            "Transfer-Encoding": "chunked",
        }
    )


@chat_bp.post("/edit")
@login_required_api
def edit_message():
    """Edit a past user message: delete it + everything after it, then regenerate."""
    data = request.get_json(force=True)
    conversation_id = data.get("conversation_id")
    message_id = data.get("message_id")
    new_text = (data.get("message") or "").strip()
    document_id = data.get("document_id")

    if not conversation_id or not message_id or not new_text:
        return jsonify(error="conversation_id, message_id and message required"), 400

    user_id = _require_user()
    sb = get_supabase_admin()

    convo = sb.table("conversations").select("id").eq("id", conversation_id).eq("user_id", user_id).execute()
    if not convo.data:
        return jsonify(error="conversation not found"), 404

    original = sb.table("messages").select("created_at").eq("id", message_id).eq("conversation_id", conversation_id).single().execute()
    if not original.data:
        return jsonify(error="message not found"), 404

    cutoff = original.data["created_at"]

    sb.table("messages").delete().eq("conversation_id", conversation_id).gte("created_at", cutoff).execute()

    return Response(
        stream_with_context(_stream_and_persist(sb, conversation_id, user_id, new_text, document_id)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
            "Transfer-Encoding": "chunked",
        }
    )


@chat_bp.get("/history")
def history():
    user_id = _require_user()
    if not user_id:
        return jsonify(conversations=[])
    sb = get_supabase_admin()
    rows = (
        sb.table("conversations")
        .select("id,title,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return jsonify(conversations=rows.data or [])


@chat_bp.get("/messages/<conversation_id>")
def messages(conversation_id: str):
    user_id = _require_user()
    if not user_id:
        return jsonify(messages=[])
    sb = get_supabase_admin()
    rows = (
        sb.table("messages")
        .select("id,role,content,created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return jsonify(messages=rows.data or [])


@chat_bp.delete("/history/<conversation_id>")
@login_required_api
def delete_conversation(conversation_id: str):
    user_id = _require_user()
    if not user_id:
        return jsonify(error="auth required"), 401
    sb = get_supabase_admin()
    convo = sb.table("conversations").select("id").eq("id", conversation_id).eq("user_id", user_id).execute()
    if not convo.data:
        return jsonify(error="conversation not found"), 404
    sb.table("messages").delete().eq("conversation_id", conversation_id).execute()
    sb.table("conversations").delete().eq("id", conversation_id).eq("user_id", user_id).execute()
    return jsonify(ok=True)


@chat_bp.post("/share/<conversation_id>")
@login_required_api
def share_conversation(conversation_id: str):
    user_id = _require_user()
    if not user_id:
        return jsonify(error="auth required"), 401
    sb = get_supabase_admin()
    convo = sb.table("conversations").select("id").eq("id", conversation_id).eq("user_id", user_id).single().execute()
    if not convo.data:
        return jsonify(error="conversation not found"), 404
    share = sb.table("shared_chats").insert({
        "conversation_id": conversation_id,
        "user_id": user_id,
    }).execute()
    share_id = share.data[0]["id"]
    return jsonify(ok=True, share_id=share_id)


@chat_bp.get("/share/<share_id>/messages")
def shared_messages(share_id: str):
    sb = get_supabase_admin()
    try:
        share = sb.table("shared_chats").select("conversation_id").eq("id", share_id).single().execute()
        if not share.data:
            return jsonify(error="Share not found"), 404
        conversation_id = share.data["conversation_id"]
        msgs = sb.table("messages").select("role,content").eq("conversation_id", conversation_id).order("created_at").execute()
        return jsonify(messages=msgs.data or [])
    except Exception as e:
        return jsonify(error=str(e)), 400


@chat_bp.get("/share/<share_id>")
def shared_chat_page(share_id: str):
    sb = get_supabase_admin()
    share = (
        sb.table("shared_chats")
        .select("id")
        .eq("id", share_id)
        .single()
        .execute()
    )
    if not share.data:
        return "Shared chat not found", 404
    return render_template("shared_chat.html", share_id=share_id)