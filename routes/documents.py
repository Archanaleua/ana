"""Document upload + listing — parses, chunks, stores in Supabase."""
from flask import Blueprint, request, jsonify, session
from services.supabase_client import get_supabase_admin
from services.parsers import extract_text
from services.rag import chunk_text

documents_bp = Blueprint("documents", __name__)


@documents_bp.post("/upload")
def upload():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(error="auth required"), 401
    if "file" not in request.files:
        return jsonify(error="file required"), 400

    f = request.files["file"]
    data = f.read()
    try:
        text = extract_text(f.filename, data)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    try:
        sb = get_supabase_admin()
        doc = sb.table("documents").insert(
        {"user_id": user_id, "name": f.filename, "content": text}
        ).execute().data[0]

        chunks = chunk_text(text)
        if chunks:
            result = sb.table("document_chunks").insert(
                [
                    {"document_id": doc["id"], "user_id": user_id,
                    "content": c, "chunk_index": i}
                    for i, c in enumerate(chunks)
                ]
            ).execute()
            

        return jsonify(ok=True, document=doc, chunks=len(chunks))

    except Exception as e:
        return jsonify(error=f"Server error: {str(e)}"), 500


@documents_bp.get("/list")
def list_docs():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(documents=[])
    sb = get_supabase_admin()
    rows = (
        sb.table("documents")
        .select("id,name,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return jsonify(documents=rows.data or [])