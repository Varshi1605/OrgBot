from __future__ import annotations

import re

from core.connectors.base import Chunk, SourceRecord

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class Chunker:
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._llama_splitter = None

    def _get_llama_splitter(self):
        if self._llama_splitter is None:
            try:
                from llama_index.core.node_parser import SentenceSplitter

                self._llama_splitter = SentenceSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.overlap,
                )
            except ImportError:
                self._llama_splitter = False
        return self._llama_splitter or None

    def split(self, text: str) -> list[str]:
        splitter = self._get_llama_splitter()
        if splitter is not None:
            from llama_index.core.schema import Document

            nodes = splitter.get_nodes_from_documents([Document(text=text)])
            return [node.get_content() for node in nodes if node.get_content().strip()]
        return self._fallback_split(text)

    def _fallback_split(self, text: str) -> list[str]:
        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
        chunks: list[str] = []
        current: list[str] = []
        current_size = 0
        for sentence in sentences:
            size = len(sentence.split())
            if current and current_size + size > self.chunk_size:
                chunks.append(" ".join(current))
                overlap_tokens = " ".join(current)[-self.overlap :].strip() if self.overlap else ""
                current = [overlap_tokens] if overlap_tokens else []
                current_size = len(overlap_tokens.split())
            current.append(sentence)
            current_size += size
        if current:
            chunks.append(" ".join(current))
        return [c for c in chunks if c.strip()]

    def chunk_record(self, record: SourceRecord) -> list[Chunk]:
        parts = self.split(record.text)
        chunks = []
        for index, part in enumerate(parts):
            chunks.append(
                Chunk(
                    chunk_id=f"{record.source}:{record.record_id}:{index}",
                    source=record.source,
                    record_id=record.record_id,
                    text=part,
                    metadata={
                        **record.metadata,
                        "source": record.source,
                        "record_id": record.record_id,
                        "timestamp": record.timestamp,
                    },
                )
            )
        return chunks
