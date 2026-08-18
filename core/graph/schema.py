from __future__ import annotations

NODE_LABELS: dict[str, dict[str, str]] = {
    "Person": {
        "name": "string",
        "team": "string",
        "role": "string",
        "slack_handle": "string",
        "github_handle": "string",
        "key": "string",
    },
    "Component": {
        "name": "string",
        "repo": "string",
        "protocol": "string",
        "version": "string",
        "owner_team": "string",
    },
    "Repository": {
        "name": "string",
        "component": "string",
        "current_version": "string",
        "language": "string",
    },
    "Team": {
        "name": "string",
        "on_call_rotation": "string",
        "slack_channel": "string",
    },
    "Incident": {
        "id": "string",
        "severity": "string",
        "title": "string",
        "status": "string",
        "rca": "string",
        "resolution_time": "float",
    },
    "Commit": {
        "hash": "string",
        "message": "string",
        "timestamp": "string",
        "branch": "string",
        "version_tag": "string",
        "repo": "string",
        "component": "string",
        "author": "string",
    },
    "Conversation": {
        "channel": "string",
        "thread_id": "string",
        "topic": "string",
        "timestamp": "string",
    },
    "Instrument": {
        "symbol": "string",
        "exchange": "string",
        "type": "string",
    },
    "Strategy": {
        "name": "string",
        "type": "string",
        "owner": "string",
    },
    "Document": {
        "path": "string",
        "component": "string",
        "doc_type": "string",
    },
}

RELATIONSHIPS: dict[str, dict] = {
    "AUTHORED": {"from": "Person", "to": "Commit", "meaning": "Engineer made this commit"},
    "OWNS": {"from": "Team", "to": "Component", "meaning": "Team is responsible for this component"},
    "WORKS_ON": {"from": "Person", "to": "Component", "meaning": "Engineer committed to this component"},
    "CAUSED_BY": {"from": "Incident", "to": "Commit", "meaning": "This commit introduced the incident"},
    "FIXED_BY": {"from": "Incident", "to": "Commit", "meaning": "This commit resolved the incident"},
    "AFFECTS": {"from": "Incident", "to": "Component", "meaning": "Incident impacted this component"},
    "RESPONDED_TO": {"from": "Person", "to": "Incident", "meaning": "Engineer was on the incident"},
    "MENTIONED_IN": {"from": "Component", "to": "Conversation", "meaning": "Component was discussed in this thread"},
    "DISCUSSED_IN": {"from": "Incident", "to": "Conversation", "meaning": "Incident war-room thread"},
    "DEPENDS_ON": {"from": "Component", "to": "Component", "meaning": "Runtime data dependency"},
    "CONSUMES_FEED": {"from": "Component", "to": "Component", "meaning": "Consumes feed output"},
    "ROUTES_ORDERS": {"from": "Component", "to": "Component", "meaning": "Routes orders via"},
    "DOCUMENTS": {"from": "Document", "to": "Component", "meaning": "Doc describes this component"},
    "PARTICIPATED_IN": {"from": "Person", "to": "Conversation", "meaning": "Person wrote in this thread"},
    "EXPERT_IN": {"from": "Person", "to": "Component", "meaning": "Engineer is an expert (derived)"},
    "FREQUENTLY_CO_AUTHORED": {"from": "Person", "to": "Person", "meaning": "Engineers co-author commits (derived)"},
    "HISTORICALLY_INCIDENT_PRONE": {
        "from": "Component",
        "to": "Instrument",
        "meaning": "Component frequently has incidents on this instrument (derived)",
    },
}

UNIQUE_CONSTRAINTS: dict[str, str] = {
    "Person": "key",
    "Component": "name",
    "Repository": "name",
    "Team": "name",
    "Incident": "id",
    "Commit": "hash",
    "Conversation": "thread_id",
    "Instrument": "symbol",
    "Strategy": "name",
    "Document": "path",
}


def constraint_cypher(label: str) -> str:
    property_name = UNIQUE_CONSTRAINTS[label]
    return (
        f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
        f"REQUIRE n.{property_name} IS UNIQUE"
    )


def all_constraints_cypher() -> list[str]:
    return [constraint_cypher(label) for label in UNIQUE_CONSTRAINTS]
