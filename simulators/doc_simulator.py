from __future__ import annotations

from pathlib import Path

from simulators._util import write_json
from simulators.org_ontology import COMPONENTS, get_team

_PROTOCOL_DETAILS: dict[str, dict] = {
    "public-feed-listener": {
        "config": "udp_port, mcast_group, subscription_file, buffer_size",
        "failure_modes": "sequence gaps, packet loss, broadcast restart, stale depth",
        "threading": "single ingestion thread, pooled normalizers, async dispatcher",
        "tuning": "buffer_size and sequence tolerance control recovery latency",
    },
    "exchange-adapter": {
        "config": "fix_target_comp, fix_sender_comp, heartbeat_interval, sequence_reset, retry_policy",
        "failure_modes": "TCP disconnect, session rejection, heartbeat timeout, partial fills",
        "threading": "per-session reader/writer threads, shared order router",
        "tuning": "heartbeat_interval and retry backoff control SLA recovery",
    },
    "orms": {
        "config": "gross_exposure_limit, notional_limit, order_throttle, position_limit, symbol_kill_switch",
        "failure_modes": "stale positions, duplicate order ids, stuck cancels, throttle hits",
        "threading": "single order state machine, parallel risk checks, sweeper thread",
        "tuning": "risk limits and throttle windows balance safety against throughput",
    },
    "trade-listener": {
        "config": "fill_topic, consumer_registry, dedup_window, backpressure_limit",
        "failure_modes": "missing fills, duplicates, out-of-order trades, downstream gaps",
        "threading": "ingest thread, dedup stage, enrichment workers, fan-out pool",
        "tuning": "dedup_window and backpressure_limit bound memory and staleness",
    },
    "strategy-interface": {
        "config": "strategy_registry, signal_rate_limit, position_sizing, config_reload_interval",
        "failure_modes": "signal drops, config reload failures, sizing errors, subscription leaks",
        "threading": "per-strategy workers, shared signal bridge, snapshot daemon",
        "tuning": "signal_rate_limit and reload interval balance responsiveness and stability",
    },
}


def _readme(component: dict) -> str:
    team = get_team(component["owner_team"])
    return (
        f"# {component['name']}\n\n"
        f"## Overview\n\n"
        f"{component['role']}.\n\n"
        f"- Protocol: {component['protocol']}\n"
        f"- Owning team: {team['name']}\n"
        f"- Repository: `{component['repo']}`\n\n"
        f"## Configuration\n\n"
        f"Key parameters: {_PROTOCOL_DETAILS[component['name']]['config']}.\n"
        f"Configuration is loaded from YAML on startup and supports hot reload for runtime parameters.\n\n"
        f"## Startup\n\n"
        f"```bash\n"
        f"python -m {component['repo']} --config config.yaml\n"
        f"```\n"
    )


def _architecture(component: dict) -> str:
    details = _PROTOCOL_DETAILS[component["name"]]
    return (
        f"# {component['name']} - Architecture\n\n"
        f"## Data Flow\n\n"
        f"{component['role']}. Incoming messages arrive over {component['protocol']} "
        f"and are validated, normalized, and dispatched to downstream consumers.\n\n"
        f"## Threading Model\n\n"
        f"{details['threading']}.\n\n"
        f"## Failure Modes\n\n"
        f"{details['failure_modes']}.\n\n"
        f"## Tuning Guide\n\n"
        f"{details['tuning']}.\n"
    )


def _runbook(component: dict) -> str:
    details = _PROTOCOL_DETAILS[component["name"]]
    return (
        f"# {component['name']} - Runbook\n\n"
        f"## On-Call\n\n"
        f"Owning team: {get_team(component['owner_team'])['name']}.\n\n"
        f"## Common Incidents\n\n"
        f"- {details['failure_modes']} - follow the checklists below.\n\n"
        f"## Escalation\n\n"
        f"1. Acknowledge the page in the on-call rotation.\n"
        f"2. Open a thread in #incidents with the incident id.\n"
        f"3. Apply the mitigation documented for the failure mode.\n"
        f"4. Escalate to the owning team lead if unresolved in 30 minutes.\n\n"
        f"## Recovery Procedure\n\n"
        f"1. Confirm connectivity to upstream/downstream dependencies.\n"
        f"2. Restart the component and verify sequence continuity.\n"
        f"3. Reconcile state with ORMS before resuming order flow.\n"
    )


def _changelog(component: dict, versions: list[str]) -> str:
    lines = [f"# {component['name']} - Changelog\n"]
    if not versions:
        lines.append("\n- **v1.0.0**: Initial release\n")
    else:
        for version in reversed(versions):
            lines.append(f"\n- **{version}**: Release snapshot\n")
    return "".join(lines)


def generate(docs_dir: Path, git_index: list[dict], seed: int) -> dict:
    versions_by_component = {}
    for index in git_index:
        versions_by_component[index["component"]] = [t["name"] for t in index["tags"]]

    result: dict[str, dict] = {}
    for component in COMPONENTS:
        component_dir = docs_dir / component["name"]
        component_dir.mkdir(parents=True, exist_ok=True)
        versions = versions_by_component.get(component["name"], ["v1.0.0"])
        files = {
            "README.md": _readme(component),
            "ARCHITECTURE.md": _architecture(component),
            "RUNBOOK.md": _runbook(component),
            "CHANGELOG.md": _changelog(component, versions),
        }
        for name, content in files.items():
            (component_dir / name).write_text(content, encoding="utf-8")
        result[component["name"]] = {
            "component": component["name"],
            "documents": list(files),
            "path": f"docs/{component['name']}",
        }
    write_json(docs_dir / "docs_index.json", result)
    return result
