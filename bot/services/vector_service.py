import os
import pickle
import logging
import numpy as np
import faiss
from bot.config import VECTORSTORE_DIR

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer("all-MiniLM-L6-v2")
    USE_EMBEDDINGS = True
    logger.info("Sentence transformer loaded.")
except Exception as e:
    logger.warning(f"sentence-transformers not available: {e}. Using keyword search fallback.")
    USE_EMBEDDINGS = False
    _model = None


def _user_index_path(user_id: int):
    d = os.path.join(VECTORSTORE_DIR, str(user_id))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "index.faiss"), os.path.join(d, "chunks.pkl")


def add_chunks_to_index(user_id: int, chunks: list[str]):
    if not chunks:
        return
    index_path, chunks_path = _user_index_path(user_id)

    existing_chunks = []
    if os.path.exists(chunks_path):
        with open(chunks_path, "rb") as f:
            existing_chunks = pickle.load(f)

    all_chunks = existing_chunks + chunks

    if USE_EMBEDDINGS and _model:
        embeddings = _model.encode(all_chunks, show_progress_bar=False, batch_size=32)
        embeddings = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(embeddings)
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        faiss.write_index(index, index_path)

    with open(chunks_path, "wb") as f:
        pickle.dump(all_chunks, f)

    logger.info(f"Indexed {len(chunks)} new chunks for user {user_id}. Total: {len(all_chunks)}")


def search_chunks(user_id: int, query: str, top_k: int = 8) -> list[str]:
    _, chunks_path = _user_index_path(user_id)
    index_path, _ = _user_index_path(user_id)

    if not os.path.exists(chunks_path):
        return []

    with open(chunks_path, "rb") as f:
        all_chunks = pickle.load(f)

    if not all_chunks:
        return []

    if USE_EMBEDDINGS and _model and os.path.exists(index_path):
        try:
            index = faiss.read_index(index_path)
            q_emb = _model.encode([query], show_progress_bar=False)
            q_emb = np.array(q_emb, dtype=np.float32)
            faiss.normalize_L2(q_emb)
            scores, indices = index.search(q_emb, min(top_k, len(all_chunks)))
            return [all_chunks[i] for i in indices[0] if i < len(all_chunks)]
        except Exception as e:
            logger.warning(f"FAISS search failed: {e}, using keyword fallback")

    return keyword_search(query, all_chunks, top_k)


def keyword_search(query: str, chunks: list[str], top_k: int = 8) -> list[str]:
    query_words = set(query.lower().split())
    scored = []
    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        score = len(query_words & chunk_words)
        scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k] if _ > 0] or chunks[:top_k]


def get_all_chunks(user_id: int) -> list[str]:
    _, chunks_path = _user_index_path(user_id)
    if not os.path.exists(chunks_path):
        return []
    with open(chunks_path, "rb") as f:
        return pickle.load(f)


def delete_user_index(user_id: int):
    index_path, chunks_path = _user_index_path(user_id)
    for path in [index_path, chunks_path]:
        if os.path.exists(path):
            os.remove(path)
    logger.info(f"Deleted index for user {user_id}")


def has_documents(user_id: int) -> bool:
    chunks = get_all_chunks(user_id)
    return len(chunks) > 0
