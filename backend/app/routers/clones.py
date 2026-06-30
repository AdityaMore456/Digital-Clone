import json
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.database import get_conn
from app.security import get_current_user
from app.vectorstore import rebuild_clone_index, chunk_text

router = APIRouter(prefix="/clones", tags=["clones"])


class ClA(BaseModel):
    name: str
    role_title: str | None = None
    headline_summary: str | None = None
    tone_preset: str = "professional_concise"


def _owned_clone_or_404(conn, clone_id: int, owner_id: int):
    row = conn.execute(
        "SELECT * FROM clones WHERE id=? AND owner_id=?", (clone_id, owner_id)
    ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clone not found.")
    return row


@router.post("")
def create_clone(payload: ClA, user=Depends(get_current_user)):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO clones (owner_id, name, role_title, headline_summary, tone_preset) "
            "VALUES (?, ?, ?, ?, ?)",
            (user["id"], payload.name, payload.role_title, payload.headline_summary, payload.tone_preset),
        )
        return {"id": cur.lastrowid}


@router.get("")
def list_my_clones(user=Depends(get_current_user)):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM clones WHERE owner_id=?", (user["id"],)).fetchall()
        return [dict(r) for r in rows]


@router.get("/{clone_id}")
def get_clone(clone_id: int, user=Depends(get_current_user)):
    with get_conn() as conn:
        return dict(_owned_clone_or_404(conn, clone_id, user["id"]))


@router.patch("/{clone_id}")
def update_clone(clone_id: int, payload: ClA, user=Depends(get_current_user)):
    with get_conn() as conn:
        _owned_clone_or_404(conn, clone_id, user["id"])
        conn.execute(
            "UPDATE clones SET name=?, role_title=?, headline_summary=?, tone_preset=? WHERE id=?",
            (payload.name, payload.role_title, payload.headline_summary, payload.tone_preset, clone_id),
        )
    return {"ok": True}


@router.post("/{clone_id}/generate")
def generate_clone(clone_id: int, user=Depends(get_current_user)):
    """FR-2.1: chunk + embed all confirmed source content into the vector index."""
    with get_conn() as conn:
        _owned_clone_or_404(conn, clone_id, user["id"])
        docs = conn.execute(
            "SELECT * FROM documents WHERE clone_id=? AND confirmed=1", (clone_id,)
        ).fetchall()
        if not docs:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No confirmed source documents yet. Confirm at least one document before generating.",
            )

        conn.execute("DELETE FROM chunks WHERE clone_id=?", (clone_id,))
        chunk_records = []
        position = 0
        for doc in docs:
            for piece in chunk_text(doc["confirmed_text"] or ""):
                conn.execute(
                    "INSERT INTO chunks (clone_id, document_id, chunk_text, vector_index_position) "
                    "VALUES (?, ?, ?, ?)",
                    (clone_id, doc["id"], piece, position),
                )
                chunk_records.append({"chunk_text": piece, "document_id": doc["id"]})
                position += 1

        rebuild_clone_index(clone_id, chunk_records)
        conn.execute(
            "UPDATE clones SET last_indexed_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), clone_id),
        )
    return {"ok": True, "chunks_indexed": len(chunk_records)}


@router.post("/{clone_id}/publish")
def publish_clone(clone_id: int, visibility: str = "public", user=Depends(get_current_user)):
    """FR-3.1: stable public link. Visibility per 7.1 (public/unlisted/private)."""
    if visibility not in ("public", "unlisted", "private"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid visibility value.")
    with get_conn() as conn:
        clone = _owned_clone_or_404(conn, clone_id, user["id"])
        slug = clone["public_slug"] or secrets.token_urlsafe(8)
        conn.execute(
            "UPDATE clones SET published=1, visibility=?, public_slug=? WHERE id=?",
            (visibility, slug, clone_id),
        )
    return {"public_slug": slug}


@router.post("/{clone_id}/unpublish")
def unpublish_clone(clone_id: int, user=Depends(get_current_user)):
    """FR-4.4: take offline without deleting underlying data."""
    with get_conn() as conn:
        _owned_clone_or_404(conn, clone_id, user["id"])
        conn.execute("UPDATE clones SET published=0 WHERE id=?", (clone_id,))
    return {"ok": True}


@router.get("/{clone_id}/conversations")
def list_conversations(clone_id: int, user=Depends(get_current_user)):
    """FR-4.1: owner views all visitor conversation logs."""
    with get_conn() as conn:
        _owned_clone_or_404(conn, clone_id, user["id"])
        convos = conn.execute(
            "SELECT * FROM conversations WHERE clone_id=? ORDER BY created_at DESC", (clone_id,)
        ).fetchall()
        result = []
        for c in convos:
            msgs = conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC", (c["id"],)
            ).fetchall()
            result.append({**dict(c), "messages": [dict(m) for m in msgs]})
        return result


@router.get("/{clone_id}/gaps")
def list_gaps(clone_id: int, user=Depends(get_current_user)):
    """FR-4.2: questions the clone couldn't answer (source-material gaps)."""
    with get_conn() as conn:
        _owned_clone_or_404(conn, clone_id, user["id"])
        rows = conn.execute(
            """SELECT m.* FROM messages m
               JOIN conversations c ON m.conversation_id = c.id
               WHERE c.clone_id=? AND m.role='clone' AND m.unanswerable=1
               ORDER BY m.created_at DESC""",
            (clone_id,),
        ).fetchall()
        return [dict(r) for r in rows]


class CorrectionIn(BaseModel):
    correction: str


@router.post("/messages/{message_id}/flag")
def flag_message(message_id: int, payload: CorrectionIn, user=Depends(get_current_user)):
    """FR-4.3: owner flags/corrects an inaccurate answer."""
    with get_conn() as conn:
        msg = conn.execute(
            """SELECT m.id, c.clone_id, cl.owner_id FROM messages m
               JOIN conversations c ON m.conversation_id = c.id
               JOIN clones cl ON c.clone_id = cl.id
               WHERE m.id=?""",
            (message_id,),
        ).fetchone()
        if not msg or msg["owner_id"] != user["id"]:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found.")
        conn.execute(
            "UPDATE messages SET flagged_inaccurate=1, owner_correction=? WHERE id=?",
            (payload.correction, message_id),
        )
    return {"ok": True}


@router.delete("/{clone_id}")
def delete_clone(clone_id: int, user=Depends(get_current_user)):
    with get_conn() as conn:
        _owned_clone_or_404(conn, clone_id, user["id"])
        conn.execute(
            "DELETE FROM messages WHERE conversation_id IN "
            "(SELECT id FROM conversations WHERE clone_id=?)", (clone_id,)
        )
        conn.execute("DELETE FROM conversations WHERE clone_id=?", (clone_id,))
        conn.execute("DELETE FROM chunks WHERE clone_id=?", (clone_id,))
        conn.execute("DELETE FROM documents WHERE clone_id=?", (clone_id,))
        conn.execute("DELETE FROM clones WHERE id=?", (clone_id,))
    return {"ok": True}


@router.delete("/account/me")
def delete_my_account(user=Depends(get_current_user)):
    """FR-4.5: permanently delete account and ALL associated data (7.1)."""
    with get_conn() as conn:
        clone_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM clones WHERE owner_id=?", (user["id"],)
        ).fetchall()]
        for clone_id in clone_ids:
            conn.execute(
                "DELETE FROM messages WHERE conversation_id IN "
                "(SELECT id FROM conversations WHERE clone_id=?)", (clone_id,)
            )
            conn.execute("DELETE FROM conversations WHERE clone_id=?", (clone_id,))
            conn.execute("DELETE FROM chunks WHERE clone_id=?", (clone_id,))
            conn.execute("DELETE FROM documents WHERE clone_id=?", (clone_id,))
        conn.execute("DELETE FROM clones WHERE owner_id=?", (user["id"],))
        conn.execute("DELETE FROM users WHERE id=?", (user["id"],))
    return {"ok": True}
