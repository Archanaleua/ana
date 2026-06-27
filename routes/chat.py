"""Chat routes — Groq inference + Supabase persistence."""
from flask import Blueprint, request, jsonify, session, render_template, Response, stream_with_context
from services.groq_client import chat as groq_chat, stream_chat
from services.supabase_client import get_supabase_admin
from services.rag import top_k
from services.auth_utils import login_required_api
import json

chat_bp = Blueprint("chat", __name__)


def _extract_memory(message: str) -> dict:
    import json
    from services.groq_client import _client
    try:
        prompt = f"""Extract personal facts from this message. Return ONLY a JSON object. If no facts found return {{}}.

CRITICAL RULES:
- "tamara" is a Gujarati word meaning "your/yours" — NEVER treat it as a name
- "tame" is Gujarati for "you" — NEVER treat it as a name
- "mane" is Gujarati for "me/I" — NEVER treat it as a name
- "kem" is Gujarati for "how" — NEVER treat it as a name
- Only extract a "name" if someone clearly introduces themselves e.g. "my name is X" or "I am X"
- Do NOT extract names from questions like "tamara naam su che"
- Store ONLY the first name in "name" key in English
- If a name is found, also provide correct transliterations in these keys:
  "name" → English/Latin version
  "name_hindi" → correct Hindi Devanagari script
  "name_gujarati" → correct Gujarati script
  "name_arabic" → correct Arabic script
  "name_russian" → correct Cyrillic script
  "name_bengali" → correct Bengali script
  "name_tamil" → correct Tamil script
  "name_telugu" → correct Telugu script
  "name_kannada" → correct Kannada script
  "name_malayalam" → correct Malayalam script
  "name_punjabi" → correct Punjabi Gurmukhi script
  "name_japanese" → correct Japanese Katakana
  "name_chinese" → correct Chinese script
  "name_korean" → correct Korean Hangul
- Use your knowledge to give the most accurate transliteration for each script
- If not a name introduction, just return other facts normally without name keys

Message: "{message}"
Return only valid JSON, nothing else."""

        resp = _client().chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=400,
            
        )
        text = resp.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        facts = json.loads(text)
        return facts if isinstance(facts, dict) else {}
    except Exception:
        return {}


def _require_user():
    return session.get("user_id")


def _detect_language(text: str) -> str:
    import re

    # ── STEP 1: Unicode script detection — instant, 100% accurate ──
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

    # ── STEP 2: Roman script — check Gujarati & Hindi FIRST before AI ──
    words = set(text.lower().split())

    # Strong Hindi signals — if any of these found → definitely Hindi
    strong_hindi = {
    "yaar", "kya", "bhai", "mujhe", "nahi", "mera", "tera",
    "haan", "chahiye", "bahut", "zyada", "abhi", "lekin",
    "raha", "rahi", "tum", "hota", "batao", "kaise", "kaisa",
    "phir", "woh", "yeh", "aur", "main", "dost", "ghar",
    # Added
    "kese", "kese ho", "kaisa", "theek", "bilkul", "shukriya",
    "dhanyawad", "namaste", "matlab", "samjha", "pata",
    "tha", "thi", "hain", "mere", "teri",
    "uska", "unka", "kyun", "kab", "kahan", "kitna", "bohot",
    }

    # Strong Gujarati signals — if any of these found → definitely Gujarati
    strong_gujarati = {
    "kem", "cho", "chhe", "nathi", "tamaru", "tamaro",
    "tamari", "aavjo", "olakho", "ghanu", "thodu", "saru",
    "maja", "bau", "javu", "avu", "tame",
    "shu", "hatu", "hati", "hata",
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

    # Hindi wins first — most important
    if words & strong_hindi and not words & strong_gujarati:
        return "Hindi"

    # Gujarati second
    if words & strong_gujarati and not words & strong_hindi:
        return "Gujarati"

    # If both found — score based decision
    hindi_score = len(words & strong_hindi)
    gujarati_score = len(words & strong_gujarati)
    if hindi_score > gujarati_score:
        return "Hindi"
    if gujarati_score > hindi_score:
        return "Gujarati"
    
    # ── STEP 2.5: Common English check before AI ──
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
    }
    if words & common_english:
        return "English"

    # ── STEP 3: AI detection for all other Roman script languages ──
    # French, Spanish, German, Italian, Portuguese, Dutch, Turkish,
    # Indonesian, Vietnamese, Malay, Swahili, and all others
    from services.groq_client import _client
    try:
        resp = _client().chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[{
                "role": "user",
                "content": (
                    f"Detect the language of this text. "
                    f"Reply with ONLY the language name in English, nothing else. "
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
        # Clean any extra text
        lang = lang.split('\n')[0].split('.')[0].strip()
        return lang if lang else "English"
    except Exception:
        return "English"


def _load_memory(sb, user_id: str) -> str | None:
    try:
        mem_rows = (
            sb.table("memory")
            .select("key,value")
            .eq("user_id", user_id)
            .limit(20)
            .execute()
        )
        if mem_rows.data:
            facts = "\n".join([f"- {m['key']}: {m['value']}" for m in mem_rows.data])
            return f"Facts about this user:\n{facts}"
    except Exception as e:
        pass
    return None  # ← returns None when memory cleared = ANA doesn't know name! ✅


def _load_context(sb, user_id: str, user_msg: str, document_id: str | None) -> str | None:
    try:
        query = sb.table("document_chunks").select("content").eq("user_id", user_id)
        if document_id:
            query = query.eq("document_id", document_id)
        chunks = query.limit(500).execute()
        chunk_contents = [c["content"] for c in (chunks.data or [])]

        if not document_id:
            return None

        if not chunk_contents:
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

        if document_id and chunk_contents:
            if any(kw in user_msg.lower() for kw in summarize_keywords) or len(user_msg.split()) <= 4:
                relevant = chunk_contents[:10]
            else:
                relevant = top_k(user_msg, chunk_contents, k=10)
        else:
            relevant = top_k(user_msg, chunk_contents, k=10)

        if relevant:
            return "\n---\n".join(relevant)

    except Exception as e:
        pass
    return None


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

    # New conversation if needed
    if not conversation_id:
        row = sb.table("conversations").insert(
            {"user_id": user_id, "title": user_msg[:60]}
        ).execute()
        conversation_id = row.data[0]["id"]

    # Load history
    msgs = (
        sb.table("messages")
        .select("role,content")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .limit(20)
        .execute()
    )
    history = (msgs.data or [])[-6:]

    memory_context = _load_memory(sb, user_id)
    context = _load_context(sb, user_id, user_msg, document_id)
    lang = _detect_language(user_msg)
    user_msg_with_hint = f"[LANG:{lang}] {user_msg}"
    messages = history + [{"role": "user", "content": user_msg_with_hint}]

    # ── STREAMING RESPONSE ──
    def generate():
        full_reply = ""
        try:
            for token in stream_chat(messages, context=context, memory=memory_context):
                full_reply += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # Save to DB after streaming done
        try:
            try:
                memory_facts = _extract_memory(user_msg)
                for key, value in memory_facts.items():
                    # Only save name if user explicitly introduced themselves
                    if key.startswith("name"):
                        # Check if message has clear name introduction
                        intro_signals = [
                            "my name is", "i am", "i'm", "mera naam", 
                            "maru naam", "call me", "naam che"
                        ]
                        if not any(signal in user_msg.lower() for signal in intro_signals):
                            continue  # skip saving name if not introduced
                    sb.table("memory").upsert({
                        "user_id": user_id,
                        "key": key,
                        "value": value,
                    }).execute()
            except Exception:
                pass

            sb.table("messages").insert([
                {"conversation_id": conversation_id, "role": "user", "content": user_msg},
                {"conversation_id": conversation_id, "role": "assistant", "content": full_reply},
            ]).execute()

            yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id, 'grounded': bool(context)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
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
        .select("role,content,created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return jsonify(messages=rows.data or [])


@chat_bp.post("/memory")
@login_required_api
def save_memory():
    user_id = _require_user()
    if not user_id:
        return jsonify(error="auth required"), 401
    data = request.get_json(force=True)
    key = data.get("key", "").strip()
    value = data.get("value", "").strip()
    if not key or not value:
        return jsonify(error="key and value required"), 400
    sb = get_supabase_admin()
    sb.table("memory").upsert({
        "user_id": user_id,
        "key": key,
        "value": value,
    }).execute()
    return jsonify(ok=True)


@chat_bp.delete("/history/<conversation_id>")
@login_required_api
def delete_conversation(conversation_id: str):
    user_id = _require_user()
    if not user_id:
        return jsonify(error="auth required"), 401
    sb = get_supabase_admin()
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