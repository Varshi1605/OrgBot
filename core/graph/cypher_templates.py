from __future__ import annotations

TEMPLATES: dict[str, str] = {
    "experts_for_component": """
        MATCH (p:Person)-[e:EXPERT_IN]->(c:Component {name: $component})
        RETURN p.name AS name, p.team AS team, e.expert_score AS expert_score
        ORDER BY expert_score DESC
        LIMIT $limit
    """,
    "incidents_for_component": """
        MATCH (i:Incident)-[:AFFECTS]->(c:Component {name: $component})
        OPTIONAL MATCH (p:Person)-[:RESPONDED_TO]->(i)
        RETURN i.id AS incident_id, i.title AS title, i.severity AS severity,
               i.rca AS rca, i.timeline AS timeline,
               collect(DISTINCT p.name) AS responders
        ORDER BY i.detected DESC
        LIMIT $limit
    """,
    "commits_for_incident": """
        MATCH (i:Incident {id: $incident_id})
        OPTIONAL MATCH (i)-[:CAUSED_BY]->(cc:Commit)
        OPTIONAL MATCH (i)-[:FIXED_BY]->(fc:Commit)
        RETURN i.id AS incident_id, i.title AS title,
               collect(DISTINCT cc.hash) AS caused_by,
               collect(DISTINCT fc.hash) AS fixed_by
    """,
    "p1_commits_for_component": """
        MATCH (i:Incident {severity: 'P1'})-[:AFFECTS]->(c:Component {name: $component})
        MATCH (f:Commit)<-[:FIXED_BY]-(i)
        RETURN i.id AS incident_id, i.title AS title,
               f.hash AS commit_hash, f.message AS message, f.timestamp AS timestamp
        ORDER BY f.timestamp DESC
        LIMIT $limit
    """,
    "slack_discussions": """
        MATCH (conv:Conversation)-[:MENTIONED_IN]-(c:Component {name: $component})
        WHERE $topic = '' OR toLower(conv.topic) CONTAINS toLower($topic)
        RETURN conv.channel AS channel, conv.thread_id AS thread_id,
               conv.timestamp AS timestamp, conv.topic AS topic
        ORDER BY conv.timestamp DESC
        LIMIT $limit
    """,
    "incident_prone_instruments": """
        MATCH (i:Incident)-[:AFFECTS]->(c:Component)
        UNWIND i.instruments AS symbol
        RETURN symbol AS instrument, c.name AS component, count(i) AS incidents
        ORDER BY incidents DESC
        LIMIT $limit
    """,
    "docs_for_component": """
        MATCH (d:Document)-[:DOCUMENTS]->(c:Component {name: $component})
        RETURN d.path AS path, d.doc_type AS doc_type
        ORDER BY d.doc_type
    """,
    "commits_matching": """
        MATCH (c:Commit)
        WHERE ($component = '' OR c.component = $component OR c.repo = $component)
          AND ($keyword = '' OR toLower(c.message) CONTAINS toLower($keyword))
        RETURN c.hash AS hash, c.message AS message, c.timestamp AS timestamp,
               c.version_tag AS version_tag, c.component AS component
        ORDER BY c.timestamp DESC
        LIMIT $limit
    """,
    "entity_neighborhood": """
        MATCH (n)
        WHERE coalesce(n.name, n.key, n.id, n.symbol, n.path) = $entity
        OPTIONAL MATCH (n)-[r]->(m)
        WITH n, collect(DISTINCT {
            relationship: type(r),
            target: coalesce(m.name, m.key, m.id, m.symbol, m.path)
        }) AS outbound
        OPTIONAL MATCH (n)<-[r2]-(m2)
        RETURN coalesce(n.name, n.key, n.id, n.symbol, n.path) AS entity,
               labels(n) AS labels,
               outbound,
               collect(DISTINCT {
                   relationship: type(r2),
                   source: coalesce(m2.name, m2.key, m2.id, m2.symbol, m2.path)
               }) AS inbound
    """,
    "component_team_contacts": """
        MATCH (t:Team)-[:OWNS]->(c:Component {name: $component})
        MATCH (p:Person {team: t.name})-[:WORKS_ON]->(c)
        RETURN p.name AS name, p.role AS role, p.slack_handle AS slack_handle
        ORDER BY p.name
    """,
}


def get_template(name: str) -> str | None:
    return TEMPLATES.get(name)
