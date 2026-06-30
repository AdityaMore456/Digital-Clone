import json
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_conn
from app.vectorstore import search_clone_index
from app.guardrails import sanitize_visitor_input, moderate_visitor_input
from app.llm import generate_clone_reply
from app.config import CHAT_RATE_LIMIT

router = APIRouter(prefix="/public", tags=["public-chat"])
limiter = Limiter(key_func=get_remote_address)


def _get_published_clone_or_404(conn, slug: str):
    row = conn.execute(
        "SELECT * FROM clones WHERE public_slug=? AND published=1", (slug,)
    ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clone not found or not published.")
    return row


@router.get("/clone/{slug}")
def get_public_clone(slug: str):
    """FR-3.2: header card (name, role, summary) before chat begins."""
    with get_conn() as conn:
        clone = _get_published_clone_or_404(conn, slug)
    starter_questions = [
        "Tell me about your projects.",
        "What technologies do you know?",
        "Walk me through your most recent role.",
        "Why should we hire you?",
    ]  # FR-3.4
    return {
        "name": clone["name"],
        "role_title": clone["role_title"],
        "headline_summary": clone["headline_summary"],
        "starter_questions": starter_questions,
        "ai_disclosure": "You are chatting with an AI clone, not the real person directly.",
    }


class StartConversationIn(BaseModel):
    visitor_name: str | None = None
    visitor_email: str | None = None


@router.post("/clone/{slug}/conversations")
def start_conversation(slug: str, payload: StartConversationIn):
    """FR-3.5: visitor contact info is strictly opt-in, never required."""
    with get_conn() as conn:
        clone = _get_published_clone_or_404(conn, slug)
        cur = conn.execute(
            "INSERT INTO conversations (clone_id, visitor_name, visitor_email) VALUES (?, ?, ?)",
            (clone["id"], payload.visitor_name, payload.visitor_email),
        )
        return {"conversation_id": cur.lastrowid}


class MessageIn(BaseModel):
    conversation_id: int
    message: str


@router.post("/clone/{slug}/messages")
@limiter.limit(CHAT_RATE_LIMIT)
def send_message(slug: str, payload: MessageIn, request: Request):
    """FR-3.1, FR-3.3, FR-3.6: core public chat endpoint."""
    with get_conn() as conn:
        clone = _get_published_clone_or_404(conn, slug)
        convo = conn.execute(
            "SELECT * FROM conversations WHERE id=? AND clone_id=?",
            (payload.conversation_id, clone["id"]),
        ).fetchone()
        if not convo:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")

        # 7.3: content moderation on visitor inputs
        if moderate_visitor_input(payload.message):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Your message was blocked by content moderation. Please rephrase.",
            )

        # FR-5.4: prompt-injection screening
        safe_message = sanitize_visitor_input(payload.message)

        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'visitor', ?)",
            (payload.conversation_id, payload.message),
        )

        history_rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
            (payload.conversation_id,),
        ).fetchall()
        history = [dict(r) for r in history_rows]

        # Strict per-clone retrieval scope — tenant isolation (8.4 high risk)
        retrieved = search_clone_index(clone["id"], safe_message, top_k=5)

        result = generate_clone_reply(
            clone_name=clone["name"],
            tone_preset=clone["tone_preset"],
            retrieved_chunks=retrieved,
            conversation_history=history,
            visitor_message=safe_message,
        )

        conn.execute(
            """INSERT INTO messages
               (conversation_id, role, content, grounded, source_document_ids, unanswerable)
               VALUES (?, 'clone', ?, ?, ?, ?)""",
            (
                payload.conversation_id,
                result["reply"],
                int(result["grounded"]),
                json.dumps(result["source_document_ids"]),
                int(result["unanswerable"]),
            ),
        )

    return {
        "reply": result["reply"],
        "grounded": result["grounded"],
        "source_document_ids": result["source_document_ids"],
    }


@router.get("/clone/{slug}/messages/{document_id}/source")
def get_source_preview(slug: str, document_id: int):
    """FR-3.3: visitor can view the source document/section backing a claim."""
    with get_conn() as conn:
        clone = _get_published_clone_or_404(conn, slug)
        doc = conn.execute(
            "SELECT id, doc_type, original_filename, source_url, confirmed_text "
            "FROM documents WHERE id=? AND clone_id=?",
            (document_id, clone["id"]),
        ).fetchone()
        if not doc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Source document not found.")
        return dict(doc)
