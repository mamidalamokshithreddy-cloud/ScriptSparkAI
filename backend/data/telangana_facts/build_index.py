import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
DOCS_PATH = Path("docs.json")
INDEX_PATH = Path("index.faiss")


def _document_text(document: Any) -> str:
    if isinstance(document, str):
        return document
    if isinstance(document, dict):
        title = str(document.get("title") or document.get("name") or "").strip()
        content = str(document.get("content") or document.get("text") or document.get("body") or "").strip()
        metadata = " ".join(str(value) for key, value in document.items() if key not in {"title", "name", "content", "text", "body"})
        return " ".join(part for part in [title, content, metadata] if part)
    return str(document)


model = SentenceTransformer(MODEL_NAME)

with DOCS_PATH.open("r", encoding="utf-8") as f:
    docs = json.load(f)

texts = [_document_text(doc) for doc in docs]
embeddings = model.encode(texts, convert_to_numpy=True)
index = faiss.IndexFlatL2(len(embeddings[0]))
index.add(np.asarray(embeddings, dtype="float32"))

faiss.write_index(index, str(INDEX_PATH))
print(f"FAISS index built and saved with {len(texts)} documents.")
