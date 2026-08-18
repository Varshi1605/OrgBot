from __future__ import annotations

import random
from datetime import timedelta
from pathlib import Path

from simulators._util import FIXED_END, FIXED_START, business_dates, iso, make_faker, make_rng, write_json
from simulators.org_ontology import CHANNELS, PEOPLE, get_channel, get_component

CHANNEL_WEIGHTS = {
    "market-data": 0.16,
    "exchange-ops": 0.16,
    "incidents": 0.16,
    "trade-ops": 0.14,
    "risk-alerts": 0.13,
    "strategy-dev": 0.13,
    "deployments": 0.12,
}

COMPONENT_BY_CHANNEL = {
    "market-data": "public-feed-listener",
    "exchange-ops": "exchange-adapter",
    "risk-alerts": "orms",
    "trade-ops": "trade-listener",
    "strategy-dev": "strategy-interface",
}

TEMPLATES: dict[str, list[str]] = {
    "market-data": [
        "Seeing sequence gaps in {component} depth for {instrument} again.",
        "Feed latency spiked after the broadcast restart.",
        "Anyone else noticing stale quotes on {instrument}?",
        "{component} dropped {n} packets in the last hour.",
        "Depth snapshots for {instrument} look delayed.",
        "Sequence monitor flagging out-of-order trades.",
    ],
    "exchange-ops": [
        "FIX session dropped, reconnecting now.",
        "ExecutionReport partial fills not parsing after deploy.",
        "Heartbeat timeout threshold increased to {s}s.",
        "Session recovery took longer than SLA, tracking.",
        "Cancel-replace race condition reappearing on {instrument}.",
        "Logon rejected for one session, checking credentials.",
    ],
    "risk-alerts": [
        "Pre-trade gross exposure check rejected {n} orders.",
        "Throttle hit on {instrument} at {n} orders/s.",
        "Stale position data caused rejections on {component}.",
        "Position limit breach detected on {component}.",
        "Duplicate order IDs reported under load.",
        "Risk params reloaded after config drift fix.",
    ],
    "trade-ops": [
        "Trade for {instrument} missing downstream, reconciling.",
        "Dedup miss on {instrument} - duplicate fill?",
        "PnL discrepancy on {component} multi-leg trade.",
        "Consumer reconnect logic handled restart cleanly.",
        "Fill mismatch between ORMS and trade listener.",
        "Trade gap detected for {instrument}, backfilling.",
    ],
    "strategy-dev": [
        "{strategy} signal rate limiting kicked in.",
        "Position sizing recalculated after config reload.",
        "Signal drop during strategy restart, investigating.",
        "State snapshot recovery worked as expected.",
        "Hot reload of risk params took effect without restart.",
        "{strategy} parameters validated on load.",
    ],
    "incidents": [
        "Incident {incident}: {title} - status update.",
        "RCA for {incident} is up. Key takeaway: {takeaway}.",
        "Action items for {incident} are tracked.",
        "Postmortem meeting for {incident} at 3pm.",
        "Escalating {incident} - on-call engaged.",
        "All hands for {incident} in the war room.",
    ],
    "deployments": [
        "Deploying {repo} v{version} to prod.",
        "Rolling back {repo} v{version}.",
        "Config change deployed for {component}.",
        "{repo} v{version} verified healthy after deploy.",
        "Canary for {repo} passed, promoting to all.",
        "Deployment window opened for {component}.",
    ],
}

REACTIONS = ["eyes", "+1", "warning", "white_check_mark", "x", "bookmark", "fire"]
TAKEAWAYS = [
    "failover automation is missing",
    "alerting thresholds were too loose",
    "a logic defect surfaced under specific market conditions",
    "capacity headroom was insufficient for peak flow",
]


def _author(rng: random.Random) -> dict:
    return rng.choice(PEOPLE)


def _mentions(rng: random.Random, exclude: str, count: int) -> list[str]:
    candidates = [p for p in PEOPLE if p["name"] != exclude]
    return [p["name"] for p in rng.sample(candidates, min(count, len(candidates)))]


def _text(rng: random.Random, channel: str, incident=None) -> str:
    template = rng.choice(TEMPLATES[channel])
    component_name = COMPONENT_BY_CHANNEL.get(channel)
    component = get_component(component_name) if component_name else get_component("orms")
    version = f"v1.{rng.randint(0, 8)}.{rng.randint(0, 9)}"
    values = {
        "component": component["name"],
        "instrument": rng.choice(["NIFTY50", "BANKNIFTY", "RELIANCE", "INFY", "TCS", "HDFC", "ICICIBANK", "SBIN"]),
        "n": str(rng.randint(10, 400)),
        "s": str(rng.randint(30, 120)),
        "strategy": rng.choice(["momentum_v1", "mean_reversion_v2", "arb_etf_v1", "vwap_execution", "pairs_nifty_banknifty"]),
        "repo": component["repo"],
        "version": version,
        "incident": incident["id"] if incident else f"INC-{rng.randint(1, 80):04d}",
        "title": incident["title"] if incident else "market data degradation",
        "takeaway": rng.choice(TAKEAWAYS),
    }
    return template.format(**values)


def _message(
    rng: random.Random,
    message_id: int,
    channel: str,
    author: str,
    text: str,
    ts,
    thread_ts: str | None,
    incident=None,
) -> dict:
    components = []
    component_name = COMPONENT_BY_CHANNEL.get(channel)
    if component_name:
        components.append(component_name)
    if incident and incident["affected_components"]:
        components.extend(incident["affected_components"])
    instruments = rng.sample(
        ["NIFTY50", "BANKNIFTY", "RELIANCE", "INFY", "TCS", "HDFC", "ICICIBANK", "SBIN"],
        rng.randint(0, 2),
    )
    reactions = [rng.choice(REACTIONS) for _ in range(rng.randint(0, 3))]
    return {
        "id": f"MS-{message_id:06d}",
        "channel": channel,
        "author": author,
        "text": text,
        "ts": iso(ts),
        "thread_ts": thread_ts,
        "reply_to": thread_ts,
        "reactions": reactions,
        "mentions": _mentions(rng, author, rng.randint(0, 2)),
        "components": sorted(set(components)),
        "instruments": instruments,
        "incident_refs": [incident["id"]] if incident else [],
    }


def generate(slack_dir: Path, incidents: list[dict], seed: int) -> list[dict]:
    rng = make_rng(seed)
    make_faker(seed)
    total = 2000
    channels = [c["name"] for c in CHANNELS]
    weights = [CHANNEL_WEIGHTS[c] for c in channels]
    channel_counts: dict[str, int] = {}
    for channel in rng.choices(channels, weights=weights, k=total):
        channel_counts[channel] = channel_counts.get(channel, 0) + 1

    by_channel = {inc["affected_components"][0]: inc for inc in incidents if inc["severity"] == "P1"}

    messages: list[dict] = []
    message_id = 1
    for channel, count in channel_counts.items():
        thread_count = max(1, count // 4)
        dates = business_dates(rng, thread_count, FIXED_START, FIXED_END)
        for t_idx in range(thread_count):
            root_ts = dates[t_idx]
            root_thread_ts = iso(root_ts)
            root_author = _author(rng)
            incident = None
            if channel == "incidents":
                if by_channel:
                    incident = rng.choice(list(by_channel.values()))
                else:
                    component_name = rng.choice(list(COMPONENT_BY_CHANNEL.values()))
                    incident = {
                        "id": f"INC-{rng.randint(1, 80):04d}",
                        "title": "market data degradation",
                        "affected_components": [component_name],
                    }
            root_text = _text(rng, channel, incident=incident)
            messages.append(
                _message(rng, message_id, channel, root_author["name"], root_text, root_ts, root_thread_ts, incident)
            )
            message_id += 1
            replies = rng.randint(2, 8)
            reply_ts = root_ts
            for _ in range(replies):
                reply_ts = reply_ts + timedelta(minutes=rng.randint(1, 120))
                if reply_ts > FIXED_END:
                    reply_ts = FIXED_END
                reply_author = _author(rng)
                reply_text = _text(rng, channel, incident=incident)
                messages.append(
                    _message(
                        rng,
                        message_id,
                        channel,
                        reply_author["name"],
                        reply_text,
                        reply_ts,
                        root_thread_ts,
                        incident,
                    )
                )
                message_id += 1

    messages = messages[:total]
    write_json(slack_dir / "slack_messages.json", messages)
    return messages
