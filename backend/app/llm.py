import json
from openai import OpenAI
from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.guardrails import build_system_prompt, asks_about_protected_class

_client = None

def get_client():
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to backend/.env before chatting."
            )
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def summarize_for_review(raw_text: str, doc_type: str) -> str:
    """Used at ingestion time so the owner can review/correct extracted
    content before it is embedded (FR-1.5)."""
    client = get_client()
    prompt = (
        f"You are structuring a candidate's {doc_type} for a professional "
        f"profile knowledge base. Reformat the following extracted text into "
        f"clean, factual bullet points. Do not invent any information that "
        f"is not present in the source text.\n\nSOURCE TEXT:\n{raw_text[:8000]}"
    )
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return resp.choices[0].message.content.strip()


def generate_clone_reply(clone_name: str, tone_preset: str, retrieved_chunks,
                          conversation_history, visitor_message: str):
    """Core RAG chat generation (FR-2.2, FR-2.3, Section 6.5 guardrails)."""
    client = get_client()
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

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.2,
    )
    raw_reply = resp.choices[0].message.content.strip()

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
    unanswerable = (not grounded) and (
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
