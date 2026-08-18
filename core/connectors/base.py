from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SourceRecord:
    source: str
    record_id: str
    text: str
    timestamp: str | None
    metadata: dict = field(default_factory=dict)
    cursor: str = ""


@dataclass
class Chunk:
    chunk_id: str
    source: str
    record_id: str
    text: str
    metadata: dict = field(default_factory=dict)


class BaseConnector(ABC):
    source: str = "base"

    def __init__(self, cursor_store=None, data_dir=None):
        self.cursor_store = cursor_store
        self.data_dir = data_dir

    @abstractmethod
    def fetch(self, cursor: str | None = None) -> list[dict]:
        pass

    @abstractmethod
    def transform(self, raw: dict) -> SourceRecord:
        pass

    def chunk(self, record: SourceRecord, chunker) -> list[Chunk]:
        return chunker.chunk_record(record)

    def get_cursor(self) -> str | None:
        if self.cursor_store is None:
            return None
        return self.cursor_store.get_cursor(self.source)

    def set_cursor(self, cursor: str) -> None:
        if self.cursor_store is not None:
            self.cursor_store.set_cursor(self.source, cursor)

    def sync(self, chunker) -> list[tuple[SourceRecord, list[Chunk]]]:
        cursor = self.get_cursor()
        raw_records = self.fetch(cursor)
        results: list[tuple[SourceRecord, list[Chunk]]] = []
        last_cursor = cursor or ""
        for raw in raw_records:
            record = self.transform(raw)
            results.append((record, self.chunk(record, chunker)))
            if record.cursor:
                last_cursor = record.cursor
        self.set_cursor(last_cursor)
        return results
