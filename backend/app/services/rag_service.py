# === FILE: backend/app/services/rag_service.py ===
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from app.config import settings
from app.utils.cache import TTLCache
from app.utils.logging import get_logger

logger = get_logger(__name__)
BASE_DIR = Path(__file__).resolve().parents[2]
WORD_RE = re.compile(r"[A-Za-z0-9\u0900-\u097F\u0C00-\u0C7F]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "about",
    "as",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "write",
    "generate",
    "story",
    "short",
}
_retrieval_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(
    ttl_seconds=settings.RAG_CACHE_TTL_SECONDS,
    max_size=128,
)


@dataclass(frozen=True)
class RagDocument:
    index: int
    title: str
    content: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RetrievalCandidate:
    document: RagDocument
    query: str
    distance: float
    similarity: float
    lexical_score: float
    rank_score: float


@dataclass(frozen=True)
class RagAssets:
    model: Any
    index: Any
    documents: list[RagDocument]
    np: Any


def _resolve_backend_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else BASE_DIR / path


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in WORD_RE.findall(text) if token.lower() not in STOP_WORDS}


def _fingerprint(text: str) -> str:
    normalized = re.sub(r"\W+", "", text.lower())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _distance_to_similarity(distance: float) -> float:
    if distance < 0 or math.isnan(distance):
        return 0.0
    return 1.0 / (1.0 + distance)


@lru_cache(maxsize=512)
def _cached_query_vector(query: str, embedding_model: str) -> tuple[float, ...]:
    assets = _load_rag_assets()
    if assets is None:
        return ()
    vector = assets.model.encode([query])[0]
    return tuple(float(value) for value in vector)


def _normalize_document(raw_doc: Any, index: int) -> Optional[RagDocument]:
    if isinstance(raw_doc, str):
        title = f"Source {index + 1}"
        content = _clean_text(raw_doc)
        metadata: dict[str, Any] = {}
    elif isinstance(raw_doc, dict):
        title = _clean_text(raw_doc.get("title") or raw_doc.get("name") or f"Source {index + 1}")
        content = _clean_text(raw_doc.get("content") or raw_doc.get("text") or raw_doc.get("body"))
        metadata = {
            key: value
            for key, value in raw_doc.items()
            if key not in {"title", "name", "content", "text", "body"} and value not in (None, "")
        }
    else:
        return None

    if not content:
        logger.warning("Skipping empty RAG document at index %s", index)
        return None

    return RagDocument(index=index, title=title, content=content, metadata=metadata)


def _load_documents(docs_path: Path) -> list[RagDocument]:
    with docs_path.open("r", encoding="utf-8") as file:
        raw_documents = json.load(file)

    if not isinstance(raw_documents, list):
        logger.warning("RAG docs file must contain a list of documents: %s", docs_path)
        return []

    documents = [
        document
        for index, raw_document in enumerate(raw_documents)
        if (document := _normalize_document(raw_document, index)) is not None
    ]
    logger.info("Loaded %s RAG documents from %s", len(documents), docs_path)
    return documents


@lru_cache(maxsize=1)
def _load_rag_assets() -> Optional[RagAssets]:
    if not settings.ENABLE_RAG:
        logger.info("RAG disabled. Set ENABLE_RAG=true to load FAISS retrieval.")
        return None

    try:
        import numpy as np

        major_version = int(np.__version__.split(".", 1)[0])
        if major_version >= 2:
            logger.warning(
                "RAG disabled because FAISS in this environment requires numpy<2. Current numpy: %s",
                np.__version__,
            )
            return None

        import faiss
        from sentence_transformers import SentenceTransformer

        index_path = _resolve_backend_path(settings.VECTORSTORE_PATH)
        docs_path = _resolve_backend_path(settings.VECTORSTORE_DOCS_PATH)

        if not index_path.exists() or not docs_path.exists():
            logger.warning("RAG assets are missing: %s / %s", index_path, docs_path)
            return None

        documents = _load_documents(docs_path)
        if not documents:
            return None

        model = SentenceTransformer(settings.RAG_EMBEDDING_MODEL)
        index = faiss.read_index(str(index_path))
        return RagAssets(model=model, index=index, documents=documents, np=np)
    except Exception as exc:
        logger.warning("RAG disabled because assets or dependencies failed to load: %s", exc)
        return None


def rewrite_query(query: str) -> list[str]:
    clean_query = _clean_text(query)
    if not clean_query:
        return []

    words = [word for word in WORD_RE.findall(clean_query) if word.lower() not in STOP_WORDS]
    keywords = " ".join(words[:12])
    title_case_terms = " ".join(term for term in re.findall(r"\b[A-Z][a-zA-Z]+\b", clean_query)[:8])

    rewrites = [
        clean_query,
        keywords,
        title_case_terms,
        f"{keywords} historical cultural factual context".strip(),
    ]

    unique_rewrites: list[str] = []
    seen: set[str] = set()
    for rewrite in rewrites:
        normalized = rewrite.lower().strip()
        if normalized and normalized not in seen:
            unique_rewrites.append(rewrite)
            seen.add(normalized)
    return unique_rewrites


def _lexical_score(query: str, document: RagDocument) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0

    doc_tokens = _tokens(f"{document.title} {document.content}")
    overlap = query_tokens.intersection(doc_tokens)
    title_overlap = query_tokens.intersection(_tokens(document.title))
    return min(1.0, (len(overlap) / len(query_tokens)) + (0.15 * len(title_overlap)))


def _rank_candidate(query: str, document: RagDocument, distance: float) -> RetrievalCandidate:
    similarity = _distance_to_similarity(distance)
    lexical_score = _lexical_score(query, document)
    metadata_boost = 0.03 if document.metadata else 0.0
    rank_score = (0.72 * similarity) + (0.25 * lexical_score) + metadata_boost
    return RetrievalCandidate(
        document=document,
        query=query,
        distance=distance,
        similarity=similarity,
        lexical_score=lexical_score,
        rank_score=rank_score,
    )


def _search_candidates(query: str, assets: RagAssets, candidate_k: int) -> list[RetrievalCandidate]:
    if not query.strip():
        return []

    vector = _cached_query_vector(query, settings.RAG_EMBEDDING_MODEL)
    if not vector:
        return []
    distances, indices = assets.index.search(assets.np.array([vector]), candidate_k)

    candidates: list[RetrievalCandidate] = []
    for raw_distance, raw_index in zip(distances[0], indices[0]):
        doc_index = int(raw_index)
        if doc_index < 0 or doc_index >= len(assets.documents):
            continue
        candidates.append(_rank_candidate(query, assets.documents[doc_index], float(raw_distance)))
    return candidates


def _deduplicate_candidates(candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
    best_by_fingerprint: dict[str, RetrievalCandidate] = {}
    for candidate in candidates:
        key = _fingerprint(f"{candidate.document.title} {candidate.document.content}")
        existing = best_by_fingerprint.get(key)
        if existing is None or candidate.rank_score > existing.rank_score:
            best_by_fingerprint[key] = candidate
    return list(best_by_fingerprint.values())


def retrieve_ranked_context(query: str, k: Optional[int] = None) -> list[dict[str, Any]]:
    assets = _load_rag_assets()
    if assets is None:
        return []

    candidate_k = max(settings.RAG_CANDIDATE_K, settings.RAG_TOP_K, k or 0)
    final_k = k or settings.RAG_TOP_K
    cache_key = f"{query.strip().lower()}::{candidate_k}::{final_k}::{settings.RAG_MIN_SIMILARITY}"
    cached = _retrieval_cache.get(cache_key)
    if cached is not None:
        logger.info("RAG cache hit for query length %s", len(query))
        return cached

    from app.chains.retrieval_chain import run_retrieval_chain

    results = run_retrieval_chain(
        query=query,
        assets=assets,
        candidate_k=candidate_k,
        top_k=final_k,
        min_similarity=settings.RAG_MIN_SIMILARITY,
    )

    _retrieval_cache.set(cache_key, results)
    logger.info("RAG retrieved %s context chunks for query length %s", len(results), len(query))
    return results


def build_structured_context(chunks: list[dict[str, Any]], max_chars: Optional[int] = None) -> str:
    if not chunks:
        return ""

    budget = max_chars or settings.RAG_MAX_CONTEXT_CHARS
    blocks: list[str] = []
    total_chars = 0

    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        metadata_text = ", ".join(f"{key}={value}" for key, value in metadata.items()) or "none"
        retrieval = chunk.get("retrieval") or {}
        block = (
            f"[{chunk.get('source_id')}] rank={chunk.get('rank')} score={retrieval.get('rank_score')}\n"
            f"Title: {chunk.get('title')}\n"
            f"Metadata: {metadata_text}\n"
            f"Content: {chunk.get('content')}"
        ).strip()

        if total_chars + len(block) > budget:
            remaining = max(0, budget - total_chars)
            if remaining > 120:
                blocks.append(block[:remaining].rstrip())
            break

        blocks.append(block)
        total_chars += len(block)

    return "\n\n---\n\n".join(blocks)


def retrieve_context(query: str, k: int = 5) -> list[dict[str, Any]]:
    return retrieve_ranked_context(query, k=k)
