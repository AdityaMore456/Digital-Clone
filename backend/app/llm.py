import json
import os
import re
import requests
from app.config import GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL
from app.guardrails import build_system_prompt, asks_about_protected_class


# Backend selection: 'local' uses a simple built-in fallback model; 'remote' calls
# the external Gemini/OpenAI-compatible endpoint. Default to remote when a
# GEMINI_API_KEY is present so the app uses Gemini by default; otherwise fall
# back to local to avoid external calls.
LLM_BACKEND = os.getenv("LLM_BACKEND", "remote" if GEMINI_API_KEY else "local").lower()


_session = None


def get_session():
    global _session
    if LLM_BACKEND != "remote":
        return None

    if _session is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to backend/.env before chatting."
            )
        s = requests.Session()
        # For Google Generative Language API endpoints we will send the API key
        # as a query parameter. For other OpenAI-compatible endpoints include a
        # bearer Authorization header.
        if "googleapis.com" not in (GEMINI_BASE_URL or ""):
            s.headers.update({
                "Authorization": f"Bearer {GEMINI_API_KEY}",
            })
        s.headers.update({"Content-Type": "application/json"})
        _session = s
    return _session


def summarize_for_review(raw_text: str, doc_type: str) -> str:
    """Used at ingestion time so the owner can review/correct extracted
    content before it is embedded (FR-1.5)."""
    # Local fallback summarizer (no external API calls)
    if LLM_BACKEND == "local":
        text = raw_text.strip()
        # Split into sentence-like chunks and use up to 5 bullets
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        bullets = sentences[:5]
        if not bullets:
            return ""
        return "\n".join(f"- {b}" for b in bullets)

    # Remote backend (external API)
    client = get_session()
    prompt = (
        f"You are structuring a candidate's {doc_type} for a professional "
        f"profile knowledge base. Reformat the following extracted text into "
        f"clean, factual bullet points. Do not invent any information that "
        f"is not present in the source text.\n\nSOURCE TEXT:\n{raw_text[:8000]}"
    )
    url = GEMINI_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": GEMINI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    params = None
    if "googleapis.com" in (GEMINI_BASE_URL or ""):
        params = {"key": GEMINI_API_KEY}
    r = client.post(url, json=payload, params=params, timeout=60)
    r.raise_for_status()
    resp = r.json()
    return resp["choices"][0]["message"]["content"].strip()


def generate_clone_reply(clone_name: str, tone_preset: str, retrieved_chunks,
                          conversation_history, visitor_message: str):
    """Core RAG chat generation (FR-2.2, FR-2.3, Section 6.5 guardrails)."""
    system_prompt = build_system_prompt(clone_name, tone_preset)

    if asks_about_protected_class(visitor_message):
        canned = (
            "I'm not able to speak to that — I can only share verified, "
            "job-relevant information from the documents I was given. Feel "
            "free to ask about specific skills, experience, or projects."
        )
        return {"reply": canned, "grounded": False, "source_document_ids": [], "unanswerable": True}

    if not retrieved_chunks:
        context_block = "(no relevant context retrieved)"
    else:
        context_block = "\n\n".join(
            f"[doc_id={c['document_id']}] {c['chunk_text']}" for c in retrieved_chunks
        )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in conversation_history[-6:]:
        role = "assistant" if turn["role"] == "clone" else "user"
        messages.append({"role": role, "content": turn["content"]})

    user_payload = (
        f"RETRIEVED CONTEXT:\n{context_block}\n\n"
        f"VISITOR QUESTION: {visitor_message}\n\n"
        f"Respond following all system rules. End your answer with a line "
        f'exactly like: SOURCES: [doc_id, doc_id] (or SOURCES: [] if none).'
    )
    messages.append({"role": "user", "content": user_payload})

    # Local backend: simple deterministic reply based on retrieved chunks
    if LLM_BACKEND == "local":
        if asks_about_protected_class(visitor_message):
            canned = (
                "I'm not able to speak to that — I can only share verified, "
                "job-relevant information from the documents I was given. Feel "
                "free to ask about specific skills, experience, or projects."
            )
            return {"reply": canned, "grounded": False, "source_document_ids": [], "unanswerable": True}

        if not retrieved_chunks:
            raw_reply = "I don't have enough information in the documents to answer that.\n\nSOURCES: []"
            source_ids = []
        else:
            # Use the first chunk as the primary source for a short, grounded reply
            first = retrieved_chunks[0]
            snippet = first.get("chunk_text", "").strip()[:500]
            raw_answer = (
                f"Based on the provided documents, here's a short answer:\n{snippet}\n\n"
                f"Answer: {visitor_message}\n\nSOURCES: [{json.dumps(first.get('document_id'))}]"
            )
            raw_reply = raw_answer
            source_ids = [first.get("document_id")]

    else:
        # Remote backend: call external API
        client = get_session()
        url = GEMINI_BASE_URL.rstrip("/") + "/chat/completions"
        payload = {"model": GEMINI_MODEL, "messages": messages, "temperature": 0.2}
        params = None
        if "googleapis.com" in (GEMINI_BASE_URL or ""):
            params = {"key": GEMINI_API_KEY}
        r = client.post(url, json=payload, params=params, timeout=60)
        r.raise_for_status()
        resp = r.json()
        raw_reply = resp["choices"][0]["message"]["content"].strip()

    # source_ids may already be set for local backend above
    if LLM_BACKEND == "local":
        reply_text = raw_reply
    else:
        source_ids = []
        reply_text = raw_reply
    if "SOURCES:" in raw_reply:
        reply_text, _, tail = raw_reply.rpartition("SOURCES:")
        reply_text = reply_text.strip()
        try:
            source_ids = json.loads(tail.strip())
        except json.JSONDecodeError:
            source_ids = []

    grounded = bool(source_ids) and bool(retrieved_chunks)
    unanswerable = False
    if not grounded:
        if not retrieved_chunks:
            # No relevant source content was available for this question,
            # record it as a knowledge gap even if the model still responded.
            unanswerable = True
        else:
            unanswerable = (
                "don't have" in reply_text.lower()
                or "do not have" in reply_text.lower()
                or "doesn't cover" in reply_text.lower()
                or "does not cover" in reply_text.lower()
            )

    return {
        "reply": reply_text,
        "grounded": grounded,
        "source_document_ids": source_ids,
        "unanswerable": unanswerable,
    }
