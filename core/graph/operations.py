from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Iterable

from core.graph.cypher_templates import get_template
from core.graph.schema import UNIQUE_CONSTRAINTS, all_constraints_cypher
from core.identity import canonical_key

ENTITY_LABELS = set(UNIQUE_CONSTRAINTS)


class Neo4jGraphStore:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self._driver

    def run(self, cypher: str, **params) -> list[dict]:
        driver = self._get_driver()
        with driver.session(database=self.database) as session:
            records = session.run(cypher, **params)
            return [record.data() for record in records]

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def is_healthy(self) -> bool:
        try:
            self.run("RETURN 1 AS ok")
            return True
        except Exception:
            return False

    def ensure_constraints(self) -> None:
        for cypher in all_constraints_cypher():
            self.run(cypher)

    def upsert_node(self, label: str, props: dict) -> None:
        _require_label(label)
        key_prop = UNIQUE_CONSTRAINTS[label]
        key_value = props.get(key_prop)
        if key_value is None:
            raise ValueError(f"{label} missing key property {key_prop}: {props}")
        safe_props = _sanitize_props({k: v for k, v in props.items() if k != key_prop})
        set_clause = ", ".join(f"n.{k} = ${k}" for k in safe_props)
        params = {"key_value": key_value, **safe_props}
        self.run(
            f"MERGE (n:{label} {{{key_prop}: $key_value}})"
            f"{f' SET {set_clause}' if set_clause else ''}",
            **params,
        )

    def upsert_many(self, label: str, records: Iterable[dict], batch_size: int = 200) -> int:
        count = 0
        batch = []
        for record in records:
            batch.append(record)
            count += 1
            if len(batch) >= batch_size:
                self._upsert_batch(label, batch)
                batch = []
        if batch:
            self._upsert_batch(label, batch)
        return count

    def _upsert_batch(self, label: str, records: list[dict]) -> None:
        _require_label(label)
        key_prop = UNIQUE_CONSTRAINTS[label]
        keys = [r.get(key_prop) for r in records]
        params_list = []
        for record in records:
            params_list.append({k: v for k, v in record.items() if k != key_prop})
        for record, param in zip(records, params_list):
            param = _sanitize_props(param)
            params = {"key_value": record[key_prop], **param}
            set_clause = ", ".join(f"n.{k} = ${k}" for k in param)
            self.run(
                f"MERGE (n:{label} {{{key_prop}: $key_value}})"
                f"{f' SET {set_clause}' if set_clause else ''}",
                **params,
            )

    def ensure_edge(
        self,
        from_label: str,
        from_key: str,
        to_label: str,
        to_key: str,
        rel_type: str,
        props: dict | None = None,
    ) -> None:
        _require_label(from_label)
        _require_label(to_label)
        from_prop = UNIQUE_CONSTRAINTS[from_label]
        to_prop = UNIQUE_CONSTRAINTS[to_label]
        rel_props = _sanitize_props(props or {})
        set_clause = ", ".join(f"r.{k} = ${k}" for k in rel_props)
        params = {
            "from_key": from_key,
            "to_key": to_key,
            **rel_props,
        }
        cypher = (
            f"MATCH (a:{from_label} {{{from_prop}: $from_key}})"
            f"MATCH (b:{to_label} {{{to_prop}: $to_key}})"
            f"MERGE (a)-[r:{rel_type}]->(b)"
        )
        if set_clause:
            cypher += f" SET {set_clause}"
        self.run(cypher, **params)

    def run_template(self, name: str, **params) -> list[dict]:
        cypher = get_template(name)
        if cypher is None:
            raise ValueError(f"Unknown cypher template: {name}")
        return self.run(cypher, **params)

    def node_counts(self) -> dict[str, int]:
        rows = self.run("MATCH (n) RETURN labels(n) AS labels, count(n) AS count")
        counts: dict[str, int] = {}
        for row in rows:
            for label in row["labels"]:
                counts[label] = counts.get(label, 0) + int(row["count"])
        return counts

    def edge_counts(self) -> dict[str, int]:
        rows = self.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count")
        return {row["type"]: int(row["count"]) for row in rows}

    def entity_neighborhood(self, entity: str, limit: int = 50) -> dict:
        rows = self.run_template("entity_neighborhood", entity=entity, limit=limit)
        if not rows:
            return {"found": False}
        row = rows[0]
        return {
            "found": True,
            "entity": row.get("entity"),
            "labels": row.get("labels", []),
            "outbound": row.get("outbound", []),
            "inbound": row.get("inbound", []),
        }


def _require_label(label: str) -> None:
    if label not in ENTITY_LABELS:
        raise ValueError(f"Unknown node label: {label}")


def _sanitize_props(props: dict) -> dict:
    clean: dict = {}
    for key, value in props.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        elif isinstance(value, (list, tuple)):
            items = list(value)
            if all(isinstance(v, (str, int, float, bool)) for v in items):
                clean[key] = [v for v in items if v is not None]
            else:
                clean[key] = json.dumps(items, sort_keys=True, default=str)
        else:
            clean[key] = json.dumps(value, sort_keys=True, default=str)
    return clean


def _parse_timeline(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def _iso_to_epoch(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _recency_weight(timestamp_epoch: float, reference_epoch: float, half_life_days: float = 180.0) -> float:
    age_days = max(0.0, (reference_epoch - timestamp_epoch) / 86400.0)
    return math.exp(-age_days / half_life_days)


def seed_ontology(store: Neo4jGraphStore, ontology: dict) -> None:
    for team in ontology["teams"].values():
        store.upsert_node("Team", {"name": team["name"], "slack_channel": team["slack_channel"]})
    for component in ontology["components"]:
        store.upsert_node(
            "Component",
            {
                "name": component["name"],
                "repo": component["repo"],
                "protocol": component["protocol"],
                "version": "",
                "owner_team": component["owner_team"],
            },
        )
        store.upsert_node(
            "Repository",
            {"name": component["repo"], "component": component["name"], "current_version": "", "language": "python"},
        )
    for person in ontology["people"]:
        store.upsert_node("Person", {**person, "key": canonical_key(person["name"])})
    for symbol in ontology["instruments"]:
        store.upsert_node("Instrument", {"symbol": symbol, "exchange": "NSE", "type": "equity-index" if symbol in ("NIFTY50", "BANKNIFTY") else "equity"})
    for strategy in ontology["strategies"]:
        store.upsert_node("Strategy", {"name": strategy["name"], "type": strategy["type"], "owner": strategy["owner_team"]})

    for team_id, team in ontology["teams"].items():
        component = next(c for c in ontology["components"] if c["owner_team"] == team_id)
        store.ensure_edge("Team", team["name"], "Component", component["name"], "OWNS")
        for member in team["members"]:
            store.ensure_edge("Person", canonical_key(member), "Component", component["name"], "WORKS_ON")
    for source, target, rel in ontology["dependencies"]:
        store.ensure_edge("Component", source, "Component", target, rel)


def ingest_entities(
    store: Neo4jGraphStore,
    entities: Iterable[dict],
    relationships: Iterable[dict],
) -> None:
    for entity in entities:
        store.upsert_node(entity["label"], entity["props"])
    for rel in relationships:
        store.ensure_edge(
            rel["source"]["label"],
            rel["source"]["key"],
            rel["target"]["label"],
            rel["target"]["key"],
            rel["type"],
            rel.get("props"),
        )


def enrich_graph(store: Neo4jGraphStore) -> None:
    _delete_derived_edges(store)
    _build_expertise_edges(store)
    _build_coauthor_edges(store)
    _build_incident_prone_edges(store)


def _delete_derived_edges(store: Neo4jGraphStore) -> None:
    store.run("MATCH (:Person)-[e:EXPERT_IN]->(:Component) DELETE e")
    store.run("MATCH (:Person)-[e:FREQUENTLY_CO_AUTHORED]->(:Person) DELETE e")
    store.run("MATCH (:Component)-[e:HISTORICALLY_INCIDENT_PRONE]->(:Instrument) DELETE e")


def _build_expertise_edges(store: Neo4jGraphStore) -> None:
    commit_rows = store.run(
        "MATCH (p:Person)-[:AUTHORED]->(c:Commit) "
        "RETURN p.key AS person, p.name AS name, c.component AS component, "
        "c.timestamp AS timestamp"
    )
    incident_rows = store.run(
        "MATCH (p:Person)-[:RESPONDED_TO]->(i:Incident)-[:AFFECTS]->(c:Component) "
        "RETURN p.key AS person, p.name AS name, c.name AS component, "
        "i.timeline AS timeline"
    )
    references = [row["timestamp"] for row in commit_rows if row.get("timestamp")]
    references += [
        t.get("resolved") or t.get("detected")
        for row in incident_rows
        for t in [_parse_timeline(row.get("timeline"))]
    ]
    reference_epoch = (
        max(_iso_to_epoch(r) for r in references) if references else datetime.now(timezone.utc).timestamp()
    )

    commit_scores: dict[tuple[str, str], float] = {}
    for row in commit_rows:
        if not row.get("component"):
            continue
        key = (row["person"], row["component"])
        commit_scores[key] = commit_scores.get(key, 0.0) + _recency_weight(
            _iso_to_epoch(row["timestamp"]), reference_epoch
        )

    incident_scores: dict[tuple[str, str], float] = {}
    for row in incident_rows:
        timeline = _parse_timeline(row.get("timeline"))
        when = timeline.get("resolved") or timeline.get("detected")
        if not when:
            continue
        key = (row["person"], row["component"])
        incident_scores[key] = incident_scores.get(key, 0.0) + _recency_weight(
            _iso_to_epoch(when), reference_epoch
        )

    all_keys = set(commit_scores) | set(incident_scores)
    if not all_keys:
        return
    commit_max = max(commit_scores.values(), default=1.0) or 1.0
    incident_max = max(incident_scores.values(), default=1.0) or 1.0
    for person_key, component in all_keys:
        normalized = 0.7 * (commit_scores.get((person_key, component), 0.0) / commit_max) + 0.3 * (
            incident_scores.get((person_key, component), 0.0) / incident_max
        )
        store.ensure_edge(
            "Person",
            person_key,
            "Component",
            component,
            "EXPERT_IN",
            {"expert_score": round(normalized, 4)},
        )


def _build_coauthor_edges(store: Neo4jGraphStore) -> None:
    rows = store.run(
        "MATCH (p:Person)-[:AUTHORED]->(c:Commit) "
        "RETURN p.key AS person, c.component AS component"
    )
    component_authors: dict[str, set[str]] = {}
    for row in rows:
        if row.get("component"):
            component_authors.setdefault(row["component"], set()).add(row["person"])
    pairs: dict[tuple[str, str], int] = {}
    for authors in component_authors.values():
        author_list = sorted(authors)
        for i, a in enumerate(author_list):
            for b in author_list[i + 1 :]:
                pair = (a, b)
                pairs[pair] = pairs.get(pair, 0) + 1
    max_shared = max(pairs.values(), default=1) or 1
    for (a, b), count in pairs.items():
        weight = round(count / max_shared, 4)
        store.ensure_edge("Person", a, "Person", b, "FREQUENTLY_CO_AUTHORED", {"weight": weight})


def _build_incident_prone_edges(store: Neo4jGraphStore) -> None:
    rows = store.run(
        "MATCH (i:Incident)-[:AFFECTS]->(c:Component) "
        "UNWIND i.instruments AS symbol "
        "MATCH (inst:Instrument {symbol: symbol}) "
        "WITH c, inst, count(i) AS cnt "
        "MERGE (c)-[h:HISTORICALLY_INCIDENT_PRONE]->(inst) "
        "SET h.incident_count = cnt "
        "RETURN c.name AS component, inst.symbol AS symbol, cnt"
    )
    return rows
