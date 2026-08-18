from __future__ import annotations

import logging
import re

from core.graph.schema import NODE_LABELS, RELATIONSHIPS
from core.identity import canonical_key

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMA_TOKENS = frozenset(NODE_LABELS) | frozenset(RELATIONSHIPS)
_TYPE_TOKEN_RE = re.compile(r":\s*([A-Z][A-Za-z0-9_]*)")
_STRING_LITERAL_RE = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")


def _unsupported_schema_token(cypher: str) -> str | None:
    cleaned = _STRING_LITERAL_RE.sub("", cypher)
    for token in _TYPE_TOKEN_RE.findall(cleaned):
        if token not in _ALLOWED_SCHEMA_TOKENS:
            return token
    return None


class VectorRetriever:
    def __init__(self, vector_store, embedder, top_k: int = 8):
        self.vector_store = vector_store
        self.embedder = embedder
        self.top_k = top_k

    def retrieve(self, query: str) -> list[dict]:
        embedding = self.embedder.embed([query])[0]
        results = self.vector_store.query(embedding, top_k=self.top_k)
        for result in results:
            result["type"] = "vector"
        return results


class GraphRetriever:
    def __init__(
        self,
        graph_store,
        ontology: dict | None = None,
        model: str | None = None,
        api_key: str | None = None,
        llm_provider: str | None = None,
        base_url: str = "http://localhost:11434",
    ):
        self.graph_store = graph_store
        self.ontology = ontology or {}
        self.model = model
        self.api_key = api_key
        self.llm_provider = llm_provider or ("anthropic" if api_key else "offline")
        self.base_url = base_url.rstrip("/")

    def _component_names(self) -> list[str]:
        return [c["name"] for c in self.ontology.get("components", [])]

    def _person_names(self) -> list[str]:
        return [p["name"] for p in self.ontology.get("people", [])]

    def _instrument_symbols(self) -> list[str]:
        return list(self.ontology.get("instruments", []))

    def _find_entity(self, query: str) -> str | None:
        normalized = query.lower().replace("-", " ").replace("_", " ")
        for component in self._component_names():
            if component.replace("-", " ") in normalized:
                return component
        for symbol in self._instrument_symbols():
            if symbol.lower() in normalized:
                return symbol
        for person in self._person_names():
            if canonical_key(person) in canonical_key(query):
                return person
        return None

    def _plan(self, query: str) -> tuple[str, dict]:
        lowered = query.lower()
        entity = self._find_entity(query) or ""
        if "incident-prone" in lowered or "incident prone" in lowered or "prone" in lowered:
            return "incident_prone_instruments", {"limit": 10}
        if "p1" in lowered:
            return "p1_commits_for_component", {"component": entity or "", "limit": 8}
        if ("owner" in lowered or "owns" in lowered or "who" in lowered) and entity:
            return "component_team_contacts", {"component": entity}
        if "expert" in lowered and entity:
            return "experts_for_component", {"component": entity, "limit": 8}
        if ("slack" in lowered or "discuss" in lowered or "thread" in lowered or "talk" in lowered) and entity:
            return "slack_discussions", {"component": entity, "topic": "", "limit": 8}
        if any(token in lowered for token in ("limit", "risk", "configure", "runbook", "parameter")) and entity:
            return "docs_for_component", {"component": entity}
        if "commit" in lowered or "change" in lowered or "recent" in lowered:
            return "commits_matching", {"component": entity or "", "keyword": "", "limit": 8}
        if ("incident" in lowered or "outage" in lowered or "breach" in lowered) and entity:
            return "incidents_for_component", {"component": entity, "limit": 8}
        if entity:
            return "entity_neighborhood", {"entity": entity, "limit": 50}
        return "commits_matching", {"component": "", "keyword": "", "limit": 8}

    def retrieve(self, query: str) -> list[dict]:
        name, params = self._plan(query)
        template_rows = self._run_template(name, params)
        facts: list[dict] = []
        if template_rows:
            facts.append({"kind": name, "facts": template_rows})
        cypher_facts = self._llm_cypher(query)
        if cypher_facts:
            facts.append({"kind": "llm_cypher", "facts": cypher_facts})
        if not facts:
            fallback_rows = self._run_template("entity_neighborhood", {"entity": "", "limit": 10})
            if fallback_rows:
                facts.append({"kind": "entity_neighborhood", "facts": fallback_rows})
        for fact in facts:
            fact["type"] = "graph"
            fact["query"] = query
        return facts

    def _run_template(self, name: str, params: dict) -> list[dict]:
        try:
            return self.graph_store.run_template(name, **params) or []
        except Exception:  # noqa: BLE001 - template failure simply means no facts
            return []

    def _llm_cypher(self, query: str) -> list[dict]:
        if self.llm_provider not in ("anthropic", "ollama"):
            return []
        allowed_rels = ", ".join(sorted(RELATIONSHIPS))
        allowed_labels = ", ".join(sorted(NODE_LABELS))
        system = (
            "You translate questions about a trading platform into read-only Cypher for Neo4j. "
            f"Allowed node labels: {allowed_labels}. "
            f"Allowed relationship types: {allowed_rels}. "
            "Return ONLY executable Cypher, no explanation, and only use the labels and "
            "relationship types listed above."
        )
        try:
            cypher = self._llm_complete(query, system=system, max_tokens=500, temperature=0.0)
        except Exception:  # noqa: BLE001 - LLM failure means no cypher facts
            return []
        if not cypher:
            return []
        cypher = re.sub(r"```(?:cypher)?", "", cypher).strip()
        if not cypher:
            return []
        unsupported = _unsupported_schema_token(cypher)
        if unsupported is not None:
            logger.warning("rejecting LLM-generated Cypher (unsupported type %r): %s", unsupported, cypher)
            return []
        try:
            rows = self.graph_store.run(cypher) or []
        except Exception:  # noqa: BLE001 - invalid cypher simply means no rows
            return []
        return rows

    def _llm_complete(self, prompt: str, system: str, max_tokens: int, temperature: float) -> str:
        if self.llm_provider == "ollama":
            import httpx

            payload = {
                "model": self.model,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            }
            with httpx.Client(timeout=300) as client:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                return response.json().get("message", {}).get("content", "")
        if self.api_key:
            from anthropic import Anthropic

            client = Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(b.text for b in response.content if b.type == "text").strip()
        return ""
