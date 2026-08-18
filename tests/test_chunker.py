from __future__ import annotations

from core.connectors.base import SourceRecord
from core.processing.chunker import Chunker


def test_split_long_text_into_multiple_chunks():
    chunker = Chunker(chunk_size=50, overlap=10)
    text = " ".join(f"Filler sentence number {i} about the trading platform." for i in range(40))
    chunks = chunker.split(text)
    assert len(chunks) > 1
    assert all(0 < len(c.split()) <= 60 for c in chunks)


def test_short_text_stays_single_chunk():
    chunker = Chunker()
    assert len(chunker.split("A short message.")) == 1


def test_chunk_record_metadata():
    chunker = Chunker(chunk_size=50, overlap=10)
    record = SourceRecord(
        source="git",
        record_id="abc123",
        text=" ".join(f"Commit detail sentence number {i}." for i in range(20)),
        timestamp="2024-01-15T10:00:00+00:00",
        metadata={"repo": "orms", "author": "Rohit Gupta"},
    )
    chunks = chunker.chunk_record(record)
    assert chunks
    assert chunks[0].chunk_id.startswith("git:abc123:")
    assert chunks[0].metadata["source"] == "git"
    assert chunks[0].metadata["record_id"] == "abc123"
    assert chunks[0].metadata["timestamp"] == "2024-01-15T10:00:00+00:00"
    assert chunks[0].metadata["repo"] == "orms"
