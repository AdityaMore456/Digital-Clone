import os
import json
import threading
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from app.config import VECTOR_DIR

_model_lock = threading.Lock()
_model = None

def get_embedder():
    """Local embedding model — no external API call needed for ingestion (9.1)."""
    global _model
    with _model_lock:
        if _model is None:
            _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_texts(texts):
    model = get_embedder()
    vectors = model.encode(texts, normalize_embeddings=True)
    return np.array(vectors, dtype="float32")


def _paths(clone_id: int):
    base = os.path.join(VECTOR_DIR, f"clone_{clone_id}")
    return base + ".index", base + ".meta.json"


def rebuild_clone_index(clone_id: int, chunk_records):
    """chunk_records: list of dicts {chunk_text, document_id}.
    Strict per-clone (per-user) namespace: each clone gets its own FAISS
    index file on disk so retrieval can never cross tenant boundaries (8.4)."""
    index_path, meta_path = _paths(clone_id)

    if not chunk_records:
        for p in (index_path, meta_path):
            if os.path.exists(p):
                os.remove(p)
        return

    texts = [r["chunk_text"] for r in chunk_records]
    vectors = embed_texts(texts)
    dim = vectors.shape[1]

    index = faiss.IndexFlatIP(dim)  # cosine similarity via normalized vectors
    index.add(vectors)
    faiss.write_index(index, index_path)

    with open(meta_path, "w") as f:
        json.dump(chunk_records, f)


def search_clone_index(clone_id: int, query: str, top_k: int = 5):
    index_path, meta_path = _paths(clone_id)
    if not (os.path.exists(index_path) and os.path.exists(meta_path)):
        return []

    index = faiss.read_index(index_path)
    with open(meta_path) as f:
        meta = json.load(f)

    q_vec = embed_texts([query])
    k = min(top_k, index.ntotal)
    if k == 0:
        return []
    scores, idxs = index.search(q_vec, k)

    results = []
    for score, idx in zip(scores[0], idxs[0]):
        if idx == -1:
            continue
        record = dict(meta[idx])
        record["score"] = float(score)
        results.append(record)
    return results


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120):
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
        if start <= 0:
            break
    return chunks
