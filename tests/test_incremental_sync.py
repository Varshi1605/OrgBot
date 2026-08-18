from __future__ import annotations

import json
import threading

from core.connectors.git_connector import GitConnector
from core.connectors.incident_connector import IncidentConnector
from core.connectors.slack_connector import SlackConnector
from core.graph.schema import UNIQUE_CONSTRAINTS
from core.processing.chunker import Chunker
from core.processing.embedder import Embedder
from core.processing.entity_extractor import EntityExtractor
from core.sync.scheduler import SyncScheduler
from ingestion.pipeline import IngestionPipeline
from simulators.org_ontology import COMPONENTS, PEOPLE, TEAMS

ONTOLOGY = {
    "people": PEOPLE,
    "components": COMPONENTS,
    "teams": TEAMS,
    "instruments": ["NIFTY50"],
    "strategies": [],
}


class FakeCursorStore:
    def __init__(self):
        self.cursors: dict[str, str] = {}

    def get_cursor(self, source: str) -> str | None:
        return self.cursors.get(source)

    def set_cursor(self, source: str, value: str) -> None:
        self.cursors[source] = value


class FakeVectorStore:
    def __init__(self):
        self.upsert_ids: list[str] = []

    def upsert_chunks(self, chunks, embeddings) -> None:
        self.upsert_ids.extend(c.chunk_id for c in chunks)


class MergeGraphStore:
    def __init__(self):
        self.nodes: dict[str, dict[str, dict]] = {}
        self.upsert_calls = 0

    def upsert_node(self, label: str, props: dict) -> None:
        self.upsert_calls += 1
        key_prop = UNIQUE_CONSTRAINTS[label]
        key = props[key_prop]
        self.nodes.setdefault(label, {}).setdefault(key, {}).update(props)

    def ensure_edge(self, *args, **kwargs) -> None:
        pass

    def run(self, cypher: str, **params):
        return []

    def run_template(self, name: str, **params):
        return []


def _write_git_index(path, commits, repo="exchange-adapter"):
    payload = [{"repo": repo, "component": repo, "commits": commits}]
    (path / "git_index.json").write_text(json.dumps(payload), encoding="utf-8")


def _make_pipeline(vector_store, graph_store):
    return IngestionPipeline(
        chunker=Chunker(),
        embedder=Embedder({"provider": "fallback", "dim": 32}),
        vector_store=vector_store,
        graph_store=graph_store,
        extractor=EntityExtractor(model="test", api_key=None, ontology=ONTOLOGY),
        ontology=ONTOLOGY,
    )


def _commit(hash_, date, message="fix", author="Rohit Gupta"):
    return {
        "hash": hash_,
        "date": date,
        "message": message,
        "author": author,
        "author_email": f"{author.lower().replace(' ', '.')}@orgbot.dev",
        "branch": "main",
        "version_tag": "",
        "files": ["src/main.py"],
    }


def test_first_sync_processes_everything_and_creates_cursor(tmp_path):
    _write_git_index(
        tmp_path,
        [
            _commit("aaa", "2024-01-01T10:00:00+00:00"),
            _commit("bbb", "2024-01-02T10:00:00+00:00"),
        ],
    )
    store = FakeCursorStore()
    connector = GitConnector(cursor_store=store, data_dir=tmp_path)
    results = connector.sync(Chunker())
    assert len(results) == 2
    assert store.get_cursor("git") == "2024-01-02T10:00:00+00:00"


def test_incremental_sync_processes_only_delta(tmp_path):
    _write_git_index(
        tmp_path,
        [
            _commit("aaa", "2024-01-01T10:00:00+00:00"),
            _commit("bbb", "2024-01-02T10:00:00+00:00"),
        ],
    )
    store = FakeCursorStore()
    connector = GitConnector(cursor_store=store, data_dir=tmp_path)
    first = connector.sync(Chunker())
    assert len(first) == 2

    second = connector.sync(Chunker())
    assert second == []

    _write_git_index(
        tmp_path,
        [
            _commit("aaa", "2024-01-01T10:00:00+00:00"),
            _commit("bbb", "2024-01-02T10:00:00+00:00"),
            _commit("ccc", "2024-01-03T10:00:00+00:00"),
        ],
    )
    third = connector.sync(Chunker())
    assert len(third) == 1
    assert third[0][0].record_id == "ccc"
    assert store.get_cursor("git") == "2024-01-03T10:00:00+00:00"


def test_slack_incremental_sync_filters_by_thread_timestamp(tmp_path):
    slack_dir = tmp_path / "slack"
    slack_dir.mkdir()
    messages = [
        {"channel": "exchange-ops", "ts": "2024-01-01T10:00:00+00:00", "thread_ts": "t1", "author": "Rohit Gupta", "text": "old", "components": []},
        {"channel": "exchange-ops", "ts": "2024-01-02T10:00:00+00:00", "thread_ts": "t2", "author": "Vikram Das", "text": "new", "components": []},
    ]
    (slack_dir / "slack_messages.json").write_text(json.dumps(messages), encoding="utf-8")

    store = FakeCursorStore()
    connector = SlackConnector(cursor_store=store, data_dir=tmp_path)
    first = connector.sync(Chunker())
    assert len(first) == 2
    second = connector.sync(Chunker())
    assert second == []


def test_incident_incremental_sync_filters_by_detected(tmp_path):
    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir()
    incidents = [
        {
            "id": "INC-0001",
            "title": "Old",
            "severity": "P1",
            "status": "resolved",
            "affected_components": ["exchange-adapter"],
            "involved_engineers": ["Rohit Gupta"],
            "instruments": [],
            "timeline": {"detected": "2024-01-01T10:00:00+00:00"},
            "rca": "",
            "action_items": [],
            "linked_commits": {"caused_by": [], "fixed_by": []},
        },
        {
            "id": "INC-0002",
            "title": "New",
            "severity": "P2",
            "status": "open",
            "affected_components": ["exchange-adapter"],
            "involved_engineers": ["Vikram Das"],
            "instruments": [],
            "timeline": {"detected": "2024-01-02T10:00:00+00:00"},
            "rca": "",
            "action_items": [],
            "linked_commits": {"caused_by": [], "fixed_by": []},
        },
    ]
    (incidents_dir / "incidents.json").write_text(json.dumps(incidents), encoding="utf-8")

    store = FakeCursorStore()
    connector = IncidentConnector(cursor_store=store, data_dir=tmp_path)
    first = connector.sync(Chunker())
    assert len(first) == 2
    second = connector.sync(Chunker())
    assert second == []


def test_rerun_same_range_creates_no_duplicate_chunks(tmp_path):
    commits = [
        _commit("aaa", "2024-01-01T10:00:00+00:00"),
        _commit("bbb", "2024-01-02T10:00:00+00:00"),
    ]
    _write_git_index(tmp_path, commits)
    store = FakeCursorStore()
    vector_store = FakeVectorStore()
    graph_store = MergeGraphStore()
    pipeline = _make_pipeline(vector_store, graph_store)
    connector = GitConnector(cursor_store=store, data_dir=tmp_path)

    records_with_chunks = connector.sync(pipeline.chunker)
    pipeline.process_records(records_with_chunks)
    first_ids = set(vector_store.upsert_ids)

    records_with_chunks = connector.sync(pipeline.chunker)
    assert records_with_chunks == []
    pipeline.process_records(records_with_chunks)
    assert set(vector_store.upsert_ids) == first_ids


def test_delta_entities_resolve_without_duplicate_nodes(tmp_path):
    _write_git_index(tmp_path, [_commit("aaa", "2024-01-01T10:00:00+00:00")])
    store = FakeCursorStore()
    graph_store = MergeGraphStore()
    vector_store = FakeVectorStore()
    pipeline = _make_pipeline(vector_store, graph_store)
    connector = GitConnector(cursor_store=store, data_dir=tmp_path)

    graph_store.upsert_node("Person", {"name": "Rohit Gupta", "key": "rohitgupta"})
    records_with_chunks = connector.sync(pipeline.chunker)
    pipeline.process_records(records_with_chunks)
    pipeline.process_records(records_with_chunks)

    assert len(graph_store.nodes.get("Person", {})) == 1
    assert len(graph_store.nodes.get("Commit", {})) == 1
    assert len(graph_store.nodes.get("Component", {})) == 1


def test_scheduler_single_flight_skips_running_source():
    started = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def sync_fn(source: str) -> None:
        calls.append(source)
        started.set()
        release.wait(2)

    scheduler = SyncScheduler(sync_fn, {"slack": 15}, run_once_at_start=False)
    first = threading.Thread(target=scheduler.sync_source, args=("slack",))
    first.start()
    assert started.wait(2)
    scheduler.sync_source("slack")
    release.set()
    first.join(2)
    assert calls == ["slack"]


def test_scheduler_syncs_all_sources_once_at_startup(monkeypatch):
    calls: list[str] = []
    intervals = {"slack": 15, "git": 60, "incidents": 1440}
    scheduler = SyncScheduler(lambda source: calls.append(source), intervals)

    class _Fake:
        def add_job(self, *args, **kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(scheduler, "_scheduler", _Fake())
    scheduler.start()
    assert sorted(calls) == ["git", "incidents", "slack"]


def test_scheduler_run_advances_cursors_and_only_new_data_syncs(tmp_path):
    slack_dir = tmp_path / "slack"
    slack_dir.mkdir()
    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir()
    _write_git_index(tmp_path, [_commit("aaa", "2024-01-01T10:00:00+00:00")])
    (slack_dir / "slack_messages.json").write_text(
        json.dumps(
            [{"channel": "ops", "ts": "2024-01-01T10:00:00+00:00", "thread_ts": "t1", "author": "Rohit Gupta", "text": "hi", "components": []}]
        ),
        encoding="utf-8",
    )
    (incidents_dir / "incidents.json").write_text(
        json.dumps(
            [
                {
                    "id": "INC-0001",
                    "title": "Old",
                    "severity": "P2",
                    "status": "resolved",
                    "affected_components": [],
                    "involved_engineers": [],
                    "instruments": [],
                    "timeline": {"detected": "2024-01-01T10:00:00+00:00"},
                    "rca": "",
                    "action_items": [],
                    "linked_commits": {"caused_by": [], "fixed_by": []},
                }
            ]
        ),
        encoding="utf-8",
    )

    store = FakeCursorStore()
    connectors = {
        "slack": SlackConnector,
        "git": GitConnector,
        "incidents": IncidentConnector,
    }
    processed: list[tuple[str, int]] = []

    def sync_fn(source: str) -> None:
        connector = connectors[source](cursor_store=store, data_dir=tmp_path)
        results = connector.sync(Chunker())
        processed.append((source, len(results)))

    scheduler = SyncScheduler(sync_fn, {"slack": 15, "git": 60, "incidents": 1440})

    class _Fake:
        def add_job(self, *args, **kwargs):
            pass

        def start(self):
            pass

    scheduler._scheduler = _Fake()

    scheduler.start()
    assert store.get_cursor("git") is not None
    assert store.get_cursor("slack") is not None
    assert store.get_cursor("incident") is not None
    assert sorted(source for source, _ in processed) == ["git", "incidents", "slack"]

    processed.clear()
    scheduler.start()
    assert all(count == 0 for _, count in processed)
