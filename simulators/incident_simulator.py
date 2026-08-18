from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

from simulators._util import FIXED_START, iso, make_faker, make_rng, write_json
from simulators.org_ontology import component_people, get_component

INCIDENT_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "public-feed-listener": [
        ("P1", "NSE {instrument} feed completely dropped"),
        ("P2", "UDP packet loss above 5 percent causing stale quotes"),
        ("P2", "Feed latency above 500ms after broadcast restart"),
        ("P3", "Sequence gap in market depth for {instrument}"),
        ("P3", "Instrument subscription filter missing for {instrument}"),
        ("P4", "Minor feed latency spike during peak hours"),
    ],
    "exchange-adapter": [
        ("P1", "FIX session not recovered within SLA"),
        ("P2", "Order acknowledgement latency above 500ms"),
        ("P2", "FIX session disconnected during peak order flow"),
        ("P3", "ExecutionReport partial fill parsing error"),
        ("P3", "Heartbeat timeout caused spurious disconnect"),
        ("P4", "Non-critical FIX log errors during reconnect"),
    ],
    "orms": [
        ("P1", "Risk system rejecting all orders due to stale position data"),
        ("P2", "Order throttle hit on {instrument}"),
        ("P2", "Gross exposure limit breach not flagged in time"),
        ("P3", "Stuck order in pending cancel state"),
        ("P3", "Duplicate order ID generated under load"),
        ("P4", "Config drift detected in risk parameters"),
    ],
    "trade-listener": [
        ("P1", "Trade listener not receiving fills after ORMS restart"),
        ("P2", "Missing trades downstream for {instrument}"),
        ("P2", "Fill mismatch between ORMS and trade listener"),
        ("P3", "Trade deduplication logic miss on {instrument}"),
        ("P3", "PnL discrepancy for {instrument} multi-leg trades"),
        ("P4", "Consumer reconnect log noise"),
    ],
    "strategy-interface": [
        ("P1", "Strategy interface down, all strategy orders blocked"),
        ("P2", "Strategy interface signal drop during restart"),
        ("P3", "Strategy config reload failed"),
        ("P3", "Position sizing miscomputed on config reload"),
        ("P3", "Signal rate limiting blocked legitimate orders"),
        ("P4", "Strategy heartbeat missed for {strategy}"),
        ("P4", "Subscription cleanup leak on strategy stop"),
    ],
}

SEVERITY_COUNTS = {"P1": 10, "P2": 20, "P3": 30, "P4": 20}

COMPONENT_WEIGHTS = {
    "public-feed-listener": 0.24,
    "exchange-adapter": 0.22,
    "orms": 0.2,
    "trade-listener": 0.18,
    "strategy-interface": 0.16,
}

ROOT_CAUSES: dict[str, str] = {
    "P1": "Loss of connectivity to the upstream exchange broadcast combined with missing failover automation delayed recovery beyond the SLA.",
    "P2": "Degraded component performance under load, compounded by insufficient alerting thresholds that delayed detection.",
    "P3": "A logic defect in the component's core processing path that surfaced under specific market conditions.",
    "P4": "Minor configuration or operational drift with no customer impact, identified during routine monitoring.",
}

ACTION_ITEMS: dict[str, list[str]] = {
    "P1": [
        "Implement automated failover for upstream connectivity",
        "Add on-call escalation for critical feed loss",
        "Document recovery runbook for the affected component",
    ],
    "P2": [
        "Add latency and packet-loss alerting thresholds",
        "Review capacity headroom for peak order flow",
        "Add regression test for the affected path",
    ],
    "P3": [
        "Fix the logic defect and add unit coverage",
        "Add integration test with realistic market data",
        "Monitor for recurrence over the next release cycle",
    ],
    "P4": [
        "Update configuration to remove configuration drift",
        "Add a periodic config drift check",
    ],
}

ALL_INSTRUMENTS = ["NIFTY50", "BANKNIFTY", "RELIANCE", "INFY", "TCS", "HDFC", "ICICIBANK", "SBIN"]


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _commit_before(commits: list[dict], when: datetime) -> str | None:
    for c in commits:
        if _parse_iso(c["date"]) <= when:
            return c["hash"]
    return commits[0]["hash"] if commits else None


def _commit_after(commits: list[dict], when: datetime) -> str | None:
    for c in commits:
        if _parse_iso(c["date"]) > when:
            return c["hash"]
    return commits[-1]["hash"] if commits else None


def _build_incident(
    rng: random.Random,
    faker,
    index: int,
    severity: str,
    component: dict,
    repo_index: dict | None,
    involved: list[dict],
    instruments: list[str],
) -> dict:
    component_name = component["name"]
    templates = [t for sev, t in INCIDENT_TEMPLATES[component_name] if sev == severity]
    template = rng.choice(templates)
    instrument = rng.choice(instruments) if instruments else "NIFTY50"
    title = template.format(instrument=instrument, strategy="momentum_v1")

    commits = repo_index["commits"] if repo_index else []
    if commits:
        available = [_parse_iso(c["date"]) for c in commits]
        detect_dt = rng.choice(available)
    else:
        detect_dt = FIXED_START

    hour_scale = {"P1": 6, "P2": 3, "P3": 2, "P4": 1}[severity]
    acked = detect_dt + timedelta(minutes=rng.randint(15, 45))
    mitigated = detect_dt + timedelta(hours=hour_scale)
    resolved = mitigated + timedelta(hours=1, minutes=rng.randint(10, 50))

    caused = _commit_before(commits, detect_dt) if commits else None
    fixed = _commit_after(commits, detect_dt) if commits else None

    rca = (
        f"{title}. {ROOT_CAUSES[severity]} "
        f"The incident affected {component_name} and was resolved after approximately {hour_scale} hours."
    )

    return {
        "id": f"INC-{index:04d}",
        "title": title,
        "severity": severity,
        "status": "resolved",
        "affected_components": [component_name],
        "involved_engineers": [p["name"] for p in involved],
        "instruments": instruments,
        "timeline": {
            "detected": iso(detect_dt),
            "acknowledged": iso(acked),
            "mitigated": iso(mitigated),
            "resolved": iso(resolved),
        },
        "rca": rca,
        "action_items": ACTION_ITEMS[severity],
        "linked_commits": {
            "caused_by": [caused] if caused else [],
            "fixed_by": [fixed] if fixed else [],
        },
    }


def generate(incidents_dir: Path, git_index: list[dict], seed: int) -> list[dict]:
    rng = make_rng(seed)
    make_faker(seed)
    repo_by_component = {idx["component"]: idx for idx in git_index}
    components = [get_component(name) for name in INCIDENT_TEMPLATES]
    weights = [COMPONENT_WEIGHTS[c["name"]] for c in components]

    incidents: list[dict] = []
    counter = 1
    for severity, count in SEVERITY_COUNTS.items():
        for _ in range(count):
            component = rng.choices(components, weights=weights, k=1)[0]
            involved = rng.sample(component_people(component["name"]), rng.randint(2, 3))
            instruments = rng.sample(ALL_INSTRUMENTS, rng.randint(0, 2))
            incident = _build_incident(
                rng,
                None,
                counter,
                severity,
                component,
                repo_by_component.get(component["name"]),
                involved,
                instruments,
            )
            incidents.append(incident)
            counter += 1

    write_json(incidents_dir / "incidents.json", incidents)
    return incidents
