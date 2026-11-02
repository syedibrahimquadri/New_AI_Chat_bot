"""Stages 4-5: embed chunks, then store them in the vector DB."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb
import numpy as np

_model: Any = None


class OnnxMiniLM:
    """all-MiniLM-L6-v2 on ONNX Runtime: same model, far less memory than PyTorch."""

    def __init__(self) -> None:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        self.embedder = ONNXMiniLM_L6_V2()
        self.embedder.DOWNLOAD_PATH = Path(__file__).resolve().parents[2] / ".models"

    def encode(self, texts: list[str], **_: Any) -> np.ndarray:
        return np.array(self.embedder(texts), dtype=np.float32)


def get_model(settings: dict[str, Any]) -> Any:
    """Single loader so ingestion and retrieval always share one model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(settings["embedding"]["model_name"])
        except ImportError:  # hosted API installs without PyTorch
            _model = OnnxMiniLM()
    return _model


def _embedding_dir(settings: dict[str, Any]) -> Path:
    return Path(settings["paths"]["chunks"]).parent / "embeddings"


def read_chunks(settings: dict[str, Any]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in sorted(Path(settings["paths"]["chunks"]).glob("*.jsonl")):
        with path.open(encoding="utf-8") as f:
            chunks.extend(json.loads(line) for line in f if line.strip())
    return chunks


def embed(settings: dict[str, Any]) -> int:
    chunks = read_chunks(settings)
    if not chunks:
        raise RuntimeError("No chunks found. Run the chunk stage first.")
    vectors = get_model(settings).encode(
        [c["text"] for c in chunks], batch_size=32, normalize_embeddings=True
    )
    out = _embedding_dir(settings)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "vectors.npy", vectors)
    (out / "ids.json").write_text(
        json.dumps(
            {
                "model": settings["embedding"]["model_name"],
                "chunk_ids": [c["chunk_id"] for c in chunks],
            }
        ),
        "utf-8",
    )
    print(f"  {vectors.shape[0]} vectors, dimension {vectors.shape[1]}")
    return int(vectors.shape[0])


def get_collection(settings: dict[str, Any], reset: bool = False):
    if settings["vector_db"]["provider"] != "chromadb":
        raise ValueError(f"Unsupported vector DB: {settings['vector_db']['provider']}")
    client = chromadb.PersistentClient(path=settings["paths"]["chroma"])
    name = settings["vector_db"]["collection"]
    if reset and name in [c.name for c in client.list_collections()]:
        client.delete_collection(name)  # rebuilt below, so removed chunks do not linger
    return client.get_or_create_collection(
        name, metadata={"hnsw:space": settings["vector_db"].get("distance", "cosine")}
    )


def store(settings: dict[str, Any]) -> int:
    chunks = {c["chunk_id"]: c for c in read_chunks(settings)}
    out = _embedding_dir(settings)
    info = json.loads((out / "ids.json").read_text("utf-8"))
    if info["model"] != settings["embedding"]["model_name"]:
        raise RuntimeError("Stored vectors use a different model. Re-run the embed stage.")
    vectors = np.load(out / "vectors.npy")
    ids = info["chunk_ids"]
    if set(ids) != set(chunks):
        raise RuntimeError("Vectors and chunks are out of sync. Re-run the embed stage.")

    collection = get_collection(settings, reset=True)
    fields = ("doc_id", "title", "scheme", "section", "source_url", "scraped_at")
    collection.upsert(
        ids=ids,
        embeddings=vectors.tolist(),
        documents=[chunks[i]["text"] for i in ids],
        metadatas=[{k: chunks[i][k] for k in fields} for i in ids],
    )
    count = collection.count()
    if count != len(ids):
        raise RuntimeError(f"Stored {count} of {len(ids)} chunks")
    print(f"  collection '{collection.name}' holds {count} chunks")
    return count
