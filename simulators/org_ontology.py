from __future__ import annotations

from core.identity import canonical_key, github_handle, slack_handle

COMPONENTS: list[dict] = [
    {
        "name": "public-feed-listener",
        "protocol": "UDP multicast (NSE)",
        "role": "Receives raw market data from NSE broadcast; normalizes and distributes internally",
        "owner_team": "market-data",
        "repo": "public-feed-listener",
    },
    {
        "name": "exchange-adapter",
        "protocol": "TCP / FIX 4.2 (NSE)",
        "role": "Manages FIX sessions with NSE; routes orders and receives acknowledgements, fills, rejections",
        "owner_team": "connectivity",
        "repo": "exchange-adapter",
    },
    {
        "name": "orms",
        "protocol": "Internal TCP/IPC",
        "role": "Order and Risk Management System; enforces pre-trade risk limits and order lifecycle",
        "owner_team": "risk-order",
        "repo": "orms",
    },
    {
        "name": "trade-listener",
        "protocol": "Internal TCP/IPC",
        "role": "Receives confirmed trade fills from ORMS; enriches and distributes downstream",
        "owner_team": "trade-processing",
        "repo": "trade-listener",
    },
    {
        "name": "strategy-interface",
        "protocol": "Internal TCP/IPC",
        "role": "API gateway between trading strategies and ORMS",
        "owner_team": "strategy",
        "repo": "strategy-interface",
    },
]

TEAMS: dict[str, dict] = {
    "market-data": {
        "name": "Market Data Team",
        "slack_channel": "market-data",
        "component": "public-feed-listener",
        "members": ["Arjun Sharma", "Priya Nair", "Ravi Iyer", "Sneha Pillai"],
    },
    "connectivity": {
        "name": "Connectivity Team",
        "slack_channel": "exchange-ops",
        "component": "exchange-adapter",
        "members": ["Vikram Das", "Ananya Menon", "Karan Mehta", "Divya Rao"],
    },
    "risk-order": {
        "name": "Risk & Order Team",
        "slack_channel": "risk-alerts",
        "component": "orms",
        "members": ["Rohit Gupta", "Meera Joshi", "Aakash Singh", "Pooja Verma"],
    },
    "trade-processing": {
        "name": "Trade Processing Team",
        "slack_channel": "trade-ops",
        "component": "trade-listener",
        "members": ["Nikhil Bhat", "Sunita Reddy", "Amit Kulkarni", "Lavanya Kumar"],
    },
    "strategy": {
        "name": "Strategy Team",
        "slack_channel": "strategy-dev",
        "component": "strategy-interface",
        "members": ["Siddharth Patil", "Deepa Nambiar", "Varun Shetty", "Ishaan Chopra"],
    },
}

ROLE_BY_TEAM = {
    "market-data": "Senior Market Data Engineer",
    "connectivity": "Senior Connectivity Engineer",
    "risk-order": "Senior Risk Engineer",
    "trade-processing": "Senior Trade Processing Engineer",
    "strategy": "Senior Strategy Engineer",
}

PEOPLE: list[dict] = []
for team_id, team in TEAMS.items():
    role = ROLE_BY_TEAM[team_id]
    for name in team["members"]:
        PEOPLE.append(
            {
                "name": name,
                "team": team_id,
                "role": role,
                "github_handle": github_handle(name),
                "slack_handle": slack_handle(name),
            }
        )

INSTRUMENTS: list[str] = [
    "NIFTY50",
    "BANKNIFTY",
    "RELIANCE",
    "INFY",
    "TCS",
    "HDFC",
    "ICICIBANK",
    "SBIN",
]

STRATEGIES: list[dict] = [
    {"name": "momentum_v1", "type": "momentum", "owner_team": "strategy"},
    {"name": "mean_reversion_v2", "type": "mean-reversion", "owner_team": "strategy"},
    {"name": "arb_etf_v1", "type": "arbitrage", "owner_team": "strategy"},
    {"name": "vwap_execution", "type": "execution", "owner_team": "strategy"},
    {"name": "pairs_nifty_banknifty", "type": "pairs", "owner_team": "strategy"},
]

CHANNELS: list[dict] = [
    {"name": "market-data", "purpose": "Feed quality and NSE data ops"},
    {"name": "exchange-ops", "purpose": "FIX session and connectivity"},
    {"name": "risk-alerts", "purpose": "Risk limit and order safety"},
    {"name": "trade-ops", "purpose": "Trade reconciliation"},
    {"name": "strategy-dev", "purpose": "Strategy performance and signals"},
    {"name": "incidents", "purpose": "Cross-component incident response"},
    {"name": "deployments", "purpose": "Release and deployment notifications"},
]

DEPENDENCIES: list[tuple[str, str, str]] = [
    ("strategy-interface", "public-feed-listener", "CONSUMES_FEED"),
    ("strategy-interface", "orms", "DEPENDS_ON"),
    ("orms", "exchange-adapter", "ROUTES_ORDERS"),
    ("trade-listener", "orms", "DEPENDS_ON"),
    ("exchange-adapter", "public-feed-listener", "DEPENDS_ON"),
]

_INDEX = {
    "person": {canonical_key(p["name"]): p for p in PEOPLE},
    "component": {c["name"]: c for c in COMPONENTS},
    "team": TEAMS,
    "instrument": {i: i for i in INSTRUMENTS},
    "strategy": {s["name"]: s for s in STRATEGIES},
    "channel": {c["name"]: c for c in CHANNELS},
}


def get_person(name: str) -> dict:
    try:
        return _INDEX["person"][canonical_key(name)]
    except KeyError:
        raise ValueError(f"Unknown person: {name}") from None


def get_component(name: str) -> dict:
    try:
        return _INDEX["component"][name]
    except KeyError:
        raise ValueError(f"Unknown component: {name}") from None


def get_team(team_id: str) -> dict:
    try:
        return _INDEX["team"][team_id]
    except KeyError:
        raise ValueError(f"Unknown team: {team_id}") from None


def get_instrument(symbol: str) -> str:
    try:
        return _INDEX["instrument"][symbol]
    except KeyError:
        raise ValueError(f"Unknown instrument: {symbol}") from None


def get_strategy(name: str) -> dict:
    try:
        return _INDEX["strategy"][name]
    except KeyError:
        raise ValueError(f"Unknown strategy: {name}") from None


def get_channel(name: str) -> dict:
    try:
        return _INDEX["channel"][name]
    except KeyError:
        raise ValueError(f"Unknown channel: {name}") from None


def people_for_team(team_id: str) -> list[dict]:
    get_team(team_id)
    return [p for p in PEOPLE if p["team"] == team_id]


def component_people(component_name: str) -> list[dict]:
    component = get_component(component_name)
    return people_for_team(component["owner_team"])


def team_for_component(component_name: str) -> dict:
    return get_team(get_component(component_name)["owner_team"])


def validate_all() -> None:
    for team_id, team in TEAMS.items():
        get_component(team["component"])
        if len(team["members"]) != 4:
            raise ValueError(f"Team {team_id} must have exactly 4 members")
        for member in team["members"]:
            get_person(member)
    for component in COMPONENTS:
        get_team(component["owner_team"])
    for source, target, rel in DEPENDENCIES:
        get_component(source)
        get_component(target)
        if rel not in {
            "DEPENDS_ON",
            "CONSUMES_FEED",
            "ROUTES_ORDERS",
        }:
            raise ValueError(f"Unknown relationship type: {rel}")
