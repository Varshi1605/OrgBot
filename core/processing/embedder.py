from __future__ import annotations

import json
import math
import os
import re
import zlib
from typing import Iterable

_WORD_RE = re.compile(r"[a-z0-9_]+")


def _sanitize_metadata(metadata: dict) -> dict:
    clean: dict = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = json.dumps(value, sort_keys=True, default=str)
    return clean


def _hash_embed(text: str, dim: int) -> list[float]:
    vector = [0.0] * dim
    for token in _WORD_RE.findall(text.lower()):
        crc = zlib.crc32(token.encode("utf-8"))
        index = crc % dim
        vector[index] += 1.0 if crc % 2 == 0 else -1.0
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [v / norm for v in vector]


class Embedder:
    def __init__(self, embedding_config: dict):
        self.provider = embedding_config.get("provider", "fallback")
        self.model = embedding_config.get("model", "voyage-3")
        self.dim = int(embedding_config.get("dim", 1024))
        self.api_key = self._api_key(embedding_config.get("api_key_env"))
        self.fallback_provider = embedding_config.get("fallback_provider")
        self.fallback_model = embedding_config.get("fallback_model")
        self.fallback_api_key = self._api_key(embedding_config.get("fallback_api_key_env"))
        self._voyage_client = None
        self._openai_client = None

    @staticmethod
    def _api_key(env_name: str | None) -> str | None:
        if not env_name:
            return None
        return os.environ.get(env_name)

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        text_list = list(texts)
        if not text_list:
            return []
        if self.provider == "voyage3" and self.api_key:
            try:
                return self._embed_voyage(text_list)
            except ImportError:
                pass
        if self.provider == "openai" and self.api_key:
            try:
                return self._embed_openai(text_list)
            except ImportError:
                pass
        if self.fallback_provider and self.fallback_api_key:
            saved = (self.provider, self.model, self.api_key)
            self.provider, self.model, self.api_key = (
                self.fallback_provider,
                self.fallback_model,
                self.fallback_api_key,
            )
            try:
                return self.embed(text_list)
            finally:
                self.provider, self.model, self.api_key = saved
        return [_hash_embed(text, self.dim) for text in text_list]

    def _embed_voyage(self, texts: list[str]) -> list[list[float]]:
        import voyageai

        if self._voyage_client is None:
            self._voyage_client = voyageai.Client(api_key=self.api_key)
        response = self._voyage_client.embed(texts, model=self.model, input_type="document")
        return [
            list(e.embedding) if hasattr(e, "embedding") else list(e)
            for e in response.embeddings
        ]

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI

        if self._openai_client is None:
            self._openai_client = OpenAI(api_key=self.api_key)
        response = self._openai_client.embeddings.create(model=self.model, input=texts)
        ordered = sorted(response.data, key=lambda d: d.index)
        return [list(d.embedding) for d in ordered]


class ChromaVectorStore:
    def __init__(
        self,
        persist_dir: str = "data/chroma",
        collection: str = "orgbot_chunks",
        host: str | None = None,
        port: int | None = None,
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection
        self.host = host
        self.port = port
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        import chromadb

        if self.host:
            client = chromadb.HttpClient(host=self.host, port=self.port or 8000)
        else:
            client = chromadb.PersistentClient(path=self.persist_dir)
        self._collection = client.get_or_create_collection(
            self.collection_name, metadata={"hnsw:space": "cosine"}
        )
        return self._collection

    def upsert_chunks(self, chunks, embeddings: list[list[float]]) -> None:
        collection = self._get_collection()
        if not chunks:
            return
        collection.upsert(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[_sanitize_metadata(c.metadata) for c in chunks],
            embeddings=embeddings,
        )

    def query(self, embedding: list[float], top_k: int = 8) -> list[dict]:
        collection = self._get_collection()
        result = collection.query(query_embeddings=[embedding], n_results=top_k)
        rows = []
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        for index, chunk_id in enumerate(ids):
            rows.append(
                {
                    "id": chunk_id,
                    "text": documents[index] if documents else "",
                    "distance": distances[index] if distances else 1.0,
                    "metadata": metadatas[index] if metadatas else {},
                }
            )
        return rows

    def count(self) -> int:
        return self._get_collection().count()

    def is_healthy(self) -> bool:
        try:
            self.count()
            return True
        except Exception:
            return False

    def delete_all(self) -> None:
        collection = self._get_collection()
        existing = collection.get()["ids"]
        if existing:
            collection.delete(ids=existing)
