from __future__ import annotations

from core.connectors.base import SourceRecord
from core.graph.operations import Neo4jGraphStore, ingest_entities
from core.processing.chunker import Chunker
from core.processing.embedder import ChromaVectorStore, Embedder
from core.processing.entity_extractor import EntityExtractor
from ingestion.graph_builder import build_graph_payload


class IngestionPipeline:
    def __init__(
        self,
        chunker: Chunker,
        embedder: Embedder,
        vector_store: ChromaVectorStore,
        graph_store: Neo4jGraphStore,
        extractor: EntityExtractor,
        ontology: dict,
    ):
        self.chunker = chunker
        self.embedder = embedder
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.extractor = extractor
        self.ontology = ontology

    def process_record(self, record: SourceRecord, chunks=None, ingest_graph: bool = True) -> dict:
        if chunks is None:
            chunks = self.chunker.chunk_record(record)
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedder.embed(texts) if texts else []
        if chunks and embeddings:
            self.vector_store.upsert_chunks(chunks, embeddings)
        if not ingest_graph:
            return {"record_id": record.record_id, "chunks": len(chunks), "entities": 0}
        extracted = self.extractor.extract(record.text, source=record.source)
        structural_entities, structural_rels = build_graph_payload(record, self.ontology)
        entities = list(extracted.get("entities", [])) + structural_entities
        relationships = list(extracted.get("relationships", [])) + structural_rels
        if entities or relationships:
            ingest_entities(self.graph_store, entities, relationships)
        return {"record_id": record.record_id, "chunks": len(chunks), "entities": len(entities)}

    def process_records(self, records_with_chunks) -> dict:
        totals = {"records": 0, "chunks": 0, "entities": 0}
        for record, chunks in records_with_chunks:
            stats = self.process_record(record, chunks)
            totals["records"] += 1
            totals["chunks"] += stats["chunks"]
            totals["entities"] += stats["entities"]
        return totals
