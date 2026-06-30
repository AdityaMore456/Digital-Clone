import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from app.config import UPLOAD_DIR
from app.database import get_conn
from app.security import get_current_user
from app.parsing import parse_uploaded_file, fetch_and_summarize_url, UnsupportedFileError
from app.llm import summarize_for_review

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_DOC_TYPES = {"resume", "linkedin", "certificate", "project_link"}


def _assert_clone_owned(conn, clone_id: int, owner_id: int):
    row = conn.execute(
        "SELECT id FROM clones WHERE id=? AND owner_id=?", (clone_id, owner_id)
    ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clone not found.")


@router.post("/upload")
async def upload_document(
    clone_id: int = Form(...),
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    """FR-1.1, FR-1.2, FR-1.4, FR-1.7."""
    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid doc_type.")

    with get_conn() as conn:
        _assert_clone_owned(conn, clone_id, user["id"])

    file_bytes = await file.read()
    try:
        raw_text = parse_uploaded_file(file.filename, doc_type, file_bytes)
    except UnsupportedFileError as e:
        # FR-1.7: clear error message, not a silent failure
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    stored_name = f"{uuid.uuid4().hex}_{file.filename}"
    stored_path = os.path.join(UPLOAD_DIR, stored_name)
    with open(stored_path, "wb") as f:
        f.write(file_bytes)

    try:
        suggested_text = summarize_for_review(raw_text, doc_type)
    except RuntimeError:
        # No LLM key configured yet — fall back to raw extracted text so the
        # upload flow still works; owner review (FR-1.5) still applies.
        suggested_text = raw_text

    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO documents
               (clone_id, doc_type, original_filename, storage_path, raw_extracted_text,
                confirmed_text, status)
               VALUES (?, ?, ?, ?, ?, ?, 'parsed')""",
            (clone_id, doc_type, file.filename, stored_path, raw_text, suggested_text),
        )
        document_id = cur.lastrowid

    return {
        "document_id": document_id,
        "doc_type": doc_type,
        "raw_extracted_text": raw_text,
        "suggested_text": suggested_text,
        "status": "parsed",
    }


class ProjectLinkIn(BaseModel):
    clone_id: int
    url: str


@router.post("/project-link")
def add_project_link(payload: ProjectLinkIn, user=Depends(get_current_user)):
    """FR-1.3: project links — fetch and summarize public content."""
    with get_conn() as conn:
        _assert_clone_owned(conn, payload.clone_id, user["id"])

    try:
        raw_text = fetch_and_summarize_url(payload.url)
    except UnsupportedFileError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    try:
        suggested_text = summarize_for_review(raw_text, "project_link")
    except RuntimeError:
        suggested_text = raw_text

    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO documents
               (clone_id, doc_type, source_url, raw_extracted_text, confirmed_text, status)
               VALUES (?, 'project_link', ?, ?, ?, 'parsed')""",
            (payload.clone_id, payload.url, raw_text, suggested_text),
        )
        document_id = cur.lastrowid

    return {"document_id": document_id, "raw_extracted_text": raw_text, "suggested_text": suggested_text}


@router.get("/clone/{clone_id}")
def list_documents(clone_id: int, user=Depends(get_current_user)):
    with get_conn() as conn:
        _assert_clone_owned(conn, clone_id, user["id"])
        rows = conn.execute("SELECT * FROM documents WHERE clone_id=?", (clone_id,)).fetchall()
        return [dict(r) for r in rows]


class ConfirmIn(BaseModel):
    confirmed_text: str


@router.post("/{document_id}/confirm")
def confirm_document(document_id: int, payload: ConfirmIn, user=Depends(get_current_user)):
    """FR-1.5: owner reviews/corrects extracted content before it is embedded."""
    with get_conn() as conn:
        doc = conn.execute(
            """SELECT d.id, d.clone_id, c.owner_id FROM documents d
               JOIN clones c ON d.clone_id = c.id WHERE d.id=?""",
            (document_id,),
        ).fetchone()
        if not doc or doc["owner_id"] != user["id"]:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
        conn.execute(
            "UPDATE documents SET confirmed_text=?, confirmed=1, status='confirmed' WHERE id=?",
            (payload.confirmed_text, document_id),
        )
    return {"ok": True}


@router.delete("/{document_id}")
def delete_document(document_id: int, user=Depends(get_current_user)):
    """FR-1.6: delete/replace a source doc; caller should re-run /generate to re-index."""
    with get_conn() as conn:
        doc = conn.execute(
            """SELECT d.id, d.storage_path, c.owner_id FROM documents d
               JOIN clones c ON d.clone_id = c.id WHERE d.id=?""",
            (document_id,),
        ).fetchone()
        if not doc or doc["owner_id"] != user["id"]:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
        if doc["storage_path"] and os.path.exists(doc["storage_path"]):
            os.remove(doc["storage_path"])
        conn.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
        conn.execute("DELETE FROM documents WHERE id=?", (document_id,))
    return {"ok": True, "note": "Re-run POST /clones/{clone_id}/generate to re-index."}
