from __future__ import annotations

import json
import re
import zlib

from core.identity import canonical_key

_INCIDENT_RE = re.compile(r"INC-\d{4}")


class EntityExtractor:
    def __init__(self, model: str, api_key: str | None = None, ontology: dict | None = None):
        self.model = model
        self.api_key = api_key
        self.ontology = ontology or {}
        self._client = None

    def _get_client(self):
        if self.api_key and self._client is None:
            try:
                from anthropic import Anthropic

                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                self._client = None
        return self._client

    def extract(self, text: str, source: str | None = None) -> dict:
        client = self._get_client()
        if client is not None:
            return self._extract_llm(text)
        return self._extract_stub(text)

    def _ontology_reference(self) -> str:
        people = [p["name"] for p in self.ontology.get("people", [])]
        components = [c["name"] for c in self.ontology.get("components", [])]
        teams = [t["name"] for t in self.ontology.get("teams", {}).values()]
        instruments = self.ontology.get("instruments", [])
        strategies = [s["name"] for s in self.ontology.get("strategies", [])]
        return (
            f"People: {', '.join(people)}\n"
            f"Components: {', '.join(components)}\n"
            f"Teams: {', '.join(teams)}\n"
            f"Instruments: {', '.join(instruments)}\n"
            f"Strategies: {', '.join(strategies)}\n"
        )

    def _extract_llm(self, text: str) -> dict:
        client = self._get_client()
        system = (
            "You extract knowledge-graph entities and relationships from chunks of "
            "engineering content (git commits, Slack threads, incident reports, docs). "
            "Only use entities from the known ontology when they match. "
            "Entity keys: Person uses the canonical key (lowercased, no spaces), "
            "Component/Team/Strategy/Instrument use their name/symbol, "
            "Incident uses its INC-xxxx id, Commit uses its hash.\n\n"
            f"Known ontology:\n{self._ontology_reference()}\n\n"
            "Return JSON matching the extract_entities tool schema."
        )
        tool = {
            "name": "extract_entities",
            "description": "Return entities and relationships found in the text.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "props": {"type": "object"},
                            },
                            "required": ["label", "props"],
                        },
                    },
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "source": {
                                    "type": "object",
                                    "properties": {"label": {"type": "string"}, "key": {"type": "string"}},
                                    "required": ["label", "key"],
                                },
                                "target": {
                                    "type": "object",
                                    "properties": {"label": {"type": "string"}, "key": {"type": "string"}},
                                    "required": ["label", "key"],
                                },
                            },
                            "required": ["type", "source", "target"],
                        },
                    },
                },
                "required": ["entities", "relationships"],
            },
        }
        response = client.messages.create(
            model=self.model,
            max_tokens=1500,
            temperature=0.0,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": "extract_entities"},
            messages=[{"role": "user", "content": text[:4000]}],
        )
        for block in response.content:
            if block.type == "tool_use":
                return block.input
        return {"entities": [], "relationships": []}

    def _extract_stub(self, text: str) -> dict:
        entities: list[dict] = []
        seen: set[tuple[str, str]] = set()

        def _add(label: str, props: dict) -> None:
            key = props.get("key") or props.get("name") or props.get("id") or props.get("symbol")
            if (label, str(key)) in seen:
                return
            seen.add((label, str(key)))
            entities.append({"label": label, "props": props})

        for person in self.ontology.get("people", []):
            if person["name"] in text:
                _add("Person", {**person, "key": canonical_key(person["name"])})
        for component in self.ontology.get("components", []):
            if component["name"] in text:
                _add("Component", {**component, "version": ""})
        for instrument in self.ontology.get("instruments", []):
            if instrument in text:
                _add("Instrument", {"symbol": instrument, "exchange": "NSE", "type": "equity"})
        for strategy in self.ontology.get("strategies", []):
            if strategy["name"] in text:
                _add("Strategy", {"name": strategy["name"], "type": strategy["type"], "owner": strategy["owner_team"]})
        for team in self.ontology.get("teams", {}).values():
            if team["name"] in text:
                _add("Team", {"name": team["name"], "slack_channel": team.get("slack_channel", "")})
        for incident_id in set(_INCIDENT_RE.findall(text)):
            _add("Incident", {"id": incident_id, "severity": "", "title": "", "status": "", "rca": ""})

        return {"entities": entities, "relationships": []}


def safe_extraction(value: str) -> dict:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"entities": [], "relationships": []}
