from __future__ import annotations

from typing import Any, Sequence

from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from pydantic import ConfigDict


class ContextualCompressionRetriever(BaseRetriever):
    base_retriever: BaseRetriever
    base_compressor: BaseDocumentCompressor
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(self, query: str, *, run_manager: Any) -> list[Document]:
        documents = self.base_retriever.invoke(query)
        compressed = self.base_compressor.compress_documents(documents, query)
        return list(compressed)


class RankedFaissRetriever(BaseRetriever):
    assets: Any
    candidate_k: int
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(self, query: str, *, run_manager: Any) -> list[Document]:
        from app.services import rag_service

        documents: list[Document] = []
        for candidate in rag_service._search_candidates(query, self.assets, self.candidate_k):
            source = candidate.document
            documents.append(
                Document(
                    page_content=source.content,
                    metadata={
                        "source_id": f"rag-{source.index + 1}",
                        "title": source.title,
                        "source_index": source.index,
                        "metadata": source.metadata,
                        "retrieval": {
                            "query": candidate.query,
                            "similarity": round(candidate.similarity, 4),
                            "lexical_score": round(candidate.lexical_score, 4),
                            "rank_score": round(candidate.rank_score, 4),
                            "distance": round(candidate.distance, 4),
                        },
                    },
                )
            )
        return documents


class RankedDocumentCompressor(BaseDocumentCompressor):
    min_similarity: float
    top_k: int

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Any | None = None,
    ) -> Sequence[Document]:
        from app.services import rag_service

        best_by_fingerprint: dict[str, Document] = {}
        for document in documents:
            retrieval = document.metadata.get("retrieval") or {}
            similarity = float(retrieval.get("similarity") or 0.0)
            lexical_score = float(retrieval.get("lexical_score") or 0.0)
            rank_score = float(retrieval.get("rank_score") or 0.0)
            if similarity < self.min_similarity and lexical_score <= 0:
                continue

            fingerprint = rag_service._fingerprint(
                f"{document.metadata.get('title', '')} {document.page_content}"
            )
            existing = best_by_fingerprint.get(fingerprint)
            existing_score = 0.0
            if existing is not None:
                existing_retrieval = existing.metadata.get("retrieval") or {}
                existing_score = float(existing_retrieval.get("rank_score") or 0.0)
            if existing is None or rank_score > existing_score:
                best_by_fingerprint[fingerprint] = document

        return sorted(
            best_by_fingerprint.values(),
            key=lambda item: float((item.metadata.get("retrieval") or {}).get("rank_score") or 0.0),
            reverse=True,
        )[: self.top_k]


def _build_compression_retriever(assets: Any, candidate_k: int, top_k: int, min_similarity: float) -> Any:
    base_retriever = RankedFaissRetriever(assets=assets, candidate_k=candidate_k)
    compressor = RankedDocumentCompressor(min_similarity=min_similarity, top_k=top_k)
    return ContextualCompressionRetriever(
        base_retriever=base_retriever,
        base_compressor=compressor,
    )


def _documents_to_chunks(documents: Sequence[Document]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for rank, document in enumerate(documents, start=1):
        retrieval = dict(document.metadata.get("retrieval") or {})
        chunks.append(
            {
                "source_id": document.metadata.get("source_id") or f"rag-{rank}",
                "rank": rank,
                "title": document.metadata.get("title") or f"Source {rank}",
                "content": document.page_content,
                "metadata": document.metadata.get("metadata") or {},
                "retrieval": retrieval,
            }
        )
    return chunks


def build_retrieval_chain(assets: Any, candidate_k: int, top_k: int, min_similarity: float) -> Any:
    compression_retriever = _build_compression_retriever(
        assets=assets,
        candidate_k=candidate_k,
        top_k=top_k,
        min_similarity=min_similarity,
    )

    def retrieve_from_rewrites(payload: dict[str, Any]) -> Sequence[Document]:
        rewritten_queries = payload["rewritten_queries"]
        query = " ".join(rewritten_queries)
        return compression_retriever.invoke(query)

    return (
        {
            "query": RunnablePassthrough(),
            "rewritten_queries": RunnableLambda(lambda query: __import__(
                "app.services.rag_service",
                fromlist=["rewrite_query"],
            ).rewrite_query(query)),
        }
        | RunnableLambda(retrieve_from_rewrites)
        | RunnableLambda(_documents_to_chunks)
    )


def run_retrieval_chain(
    query: str,
    assets: Any,
    candidate_k: int,
    top_k: int,
    min_similarity: float,
) -> list[dict[str, Any]]:
    chunks = build_retrieval_chain(
        assets=assets,
        candidate_k=candidate_k,
        top_k=top_k,
        min_similarity=min_similarity,
    ).invoke(query)
    return chunks if isinstance(chunks, list) else []
