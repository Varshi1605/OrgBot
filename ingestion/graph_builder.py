from __future__ import annotations

from datetime import datetime, timezone

from core.connectors.base import SourceRecord
from core.identity import canonical_key


def _person_ref(name: str, ontology: dict) -> dict:
    key = canonical_key(name)
    person = next((p for p in ontology.get("people", []) if canonical_key(p["name"]) == key), None)
    if person is None:
        return {"label": "Person", "key": key}
    return {"label": "Person", "key": key}


def _component_ref(name: str) -> dict:
    return {"label": "Component", "key": name}


def _commit_ref(commit_hash: str) -> dict:
    return {"label": "Commit", "key": commit_hash}


def _incident_ref(incident_id: str) -> dict:
    return {"label": "Incident", "key": incident_id}


def _resolution_hours(timeline: dict) -> float | None:
    detected = timeline.get("detected")
    resolved = timeline.get("resolved")
    if not detected or not resolved:
        return None
    try:
        start = datetime.fromisoformat(detected.replace("Z", "+00:00"))
        end = datetime.fromisoformat(resolved.replace("Z", "+00:00"))
        return round((end - start).total_seconds() / 3600.0, 2)
    except ValueError:
        return None


def build_graph_payload(record: SourceRecord, ontology: dict) -> tuple[list[dict], list[dict]]:
    builder = _Builder(record, ontology)
    return builder.build()


class _Builder:
    def __init__(self, record: SourceRecord, ontology: dict):
        self.record = record
        self.ontology = ontology
        self.entities: list[dict] = []
        self.relationships: list[dict] = []

    def build(self) -> tuple[list[dict], list[dict]]:
        source = self.record.source
        if source == "git":
            self._git()
        elif source == "slack":
            self._slack()
        elif source == "incident":
            self._incident()
        elif source == "docs":
            self._docs()
        return self.entities, self.relationships

    def _entity(self, label: str, props: dict) -> dict:
        self.entities.append({"label": label, "props": props})
        return {"label": label, "key": props.get("key") or props.get("name") or props.get("id") or props.get("hash") or props.get("symbol") or props.get("path")}

    def _rel(self, rel_type: str, source: dict, target: dict, props: dict | None = None) -> None:
        self.relationships.append({"type": rel_type, "source": source, "target": target, "props": props})

    def _git(self) -> None:
        m = self.record.metadata
        commit = self._entity(
            "Commit",
            {
                "hash": self.record.record_id,
                "message": m.get("message", "") or self.record.text.split("\n")[0][len(f"[{m.get('repo', '')}] "):],
                "timestamp": self.record.timestamp,
                "branch": m.get("branch"),
                "version_tag": m.get("version_tag"),
                "repo": m.get("repo"),
                "component": m.get("component"),
                "author": m.get("author"),
            },
        )
        person = _person_ref(m.get("author") or "", self.ontology)
        self._rel("AUTHORED", person, commit)
        if m.get("component"):
            self._rel("WORKS_ON", person, _component_ref(m["component"]))

    def _slack(self) -> None:
        m = self.record.metadata
        conversation = self._entity(
            "Conversation",
            {
                "channel": m.get("channel"),
                "thread_id": m.get("thread_id"),
                "topic": m.get("topic"),
                "timestamp": self.record.timestamp,
            },
        )
        for author in m.get("authors", []):
            self._rel("PARTICIPATED_IN", _person_ref(author, self.ontology), conversation)
        for component in m.get("components", []):
            self._rel("MENTIONED_IN", _component_ref(component), conversation)
        for incident_id in m.get("incident_refs", []):
            self._rel("DISCUSSED_IN", _incident_ref(incident_id), conversation)

    def _incident(self) -> None:
        m = self.record.metadata
        incident = self._entity(
            "Incident",
            {
                "id": m.get("id"),
                "severity": m.get("severity"),
                "title": m.get("title"),
                "status": m.get("status"),
                "rca": m.get("rca"),
                "timeline": m.get("timeline", {}),
                "instruments": m.get("instruments", []),
                "resolution_time": _resolution_hours(m.get("timeline", {})),
                "detected": (m.get("timeline") or {}).get("detected"),
            },
        )
        for component in m.get("affected_components", []):
            self._rel("AFFECTS", incident, _component_ref(component))
        for engineer in m.get("involved_engineers", []):
            self._rel("RESPONDED_TO", _person_ref(engineer, self.ontology), incident)
        linked = m.get("linked_commits", {})
        for commit_hash in linked.get("caused_by", []):
            self._rel("CAUSED_BY", incident, _commit_ref(commit_hash))
        for commit_hash in linked.get("fixed_by", []):
            self._rel("FIXED_BY", incident, _commit_ref(commit_hash))

    def _docs(self) -> None:
        m = self.record.metadata
        document = self._entity(
            "Document",
            {"path": m.get("path"), "component": m.get("component"), "doc_type": m.get("doc_type")},
        )
        if m.get("component"):
            self._rel("DOCUMENTS", document, _component_ref(m["component"]))
