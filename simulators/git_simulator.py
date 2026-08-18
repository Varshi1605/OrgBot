from __future__ import annotations

import random
import subprocess
from datetime import datetime
from pathlib import Path

from core.identity import github_handle
from simulators._util import FIXED_END, FIXED_START, business_dates, iso, make_rng, write_json
from simulators.org_ontology import COMPONENTS, component_people

COMMIT_MESSAGES: dict[str, list[str]] = {
    "public-feed-listener": [
        "Fix UDP sequence gap detection in market depth handler",
        "Add instrument subscription filtering for NIFTY derivatives",
        "Handle NSE broadcast restart gracefully",
        "Improve packet loss recovery in feed buffer",
        "Add latency histogram for feed processing",
        "Normalize depth snapshots for {instrument}",
        "Refactor feed dispatcher to decouple sequence validation",
        "Reduce heap churn in quote normalization path",
        "Add feed status heartbeat publishing",
        "Handle out-of-order trade messages in tape",
    ],
    "exchange-adapter": [
        "Handle FIX session recovery after TCP disconnect",
        "Fix order cancel-replace race condition",
        "Add support for IOC order type",
        "Parse ExecutionReport for partial fill correctly",
        "Implement heartbeat timeout detection",
        "Add FIX session sequence reset on logon rejection",
        "Retry order transmission with exponential backoff",
        "Validate tag 35 message types before dispatch",
        "Add session-level rate limiting for outbound orders",
        "Fix ExecutionReport duplication on reconnect",
    ],
    "orms": [
        "Add pre-trade risk check for gross exposure limit",
        "Fix order state machine transition for pending cancel",
        "Implement position limit breach rejection",
        "Add order throttle per instrument per second",
        "Fix duplicate order ID generation under load",
        "Enforce max notional check before order entry",
        "Add stuck order sweeper for orphaned orders",
        "Persist order snapshots for crash recovery",
        "Add symbol-level kill switch for {instrument}",
        "Fix cancel handling when order already filled",
    ],
    "trade-listener": [
        "Fix trade deduplication when fill arrives out of order",
        "Add trade enrichment with strategy metadata",
        "Handle partial fill aggregation correctly",
        "Add downstream consumer reconnect logic",
        "Fix PnL calculation for multi-leg trades",
        "Add trade gap detection for downstream consumers",
        "Normalize instrument codes in trade records",
        "Add position sync with ORMS after reconciliation",
        "Fix timestamp drift between fill and trade records",
        "Add trade fan-out backpressure handling",
    ],
    "strategy-interface": [
        "Add momentum strategy signal rate limiting",
        "Fix position sizing calculation on config reload",
        "Implement strategy state snapshot for recovery",
        "Add hot reload for risk parameter changes",
        "Fix signal drop during strategy restart",
        "Add {strategy} parameter validation on load",
        "Refactor strategy lifecycle management",
        "Add order intent deduplication across restarts",
        "Expose strategy heartbeat to monitoring",
        "Fix subscription cleanup on strategy stop",
    ],
}

FILES: dict[str, list[str]] = {
    "public-feed-listener": [
        "src/feed_listener.py",
        "src/depth_handler.py",
        "src/sequence_monitor.py",
        "src/udp_socket.py",
        "src/quote_normalizer.py",
        "src/trade_tape.py",
        "src/status_publisher.py",
        "tests/test_depth_handler.py",
        "tests/test_sequence_monitor.py",
    ],
    "exchange-adapter": [
        "src/fix_session.py",
        "src/execution_parser.py",
        "src/order_router.py",
        "src/heartbeat.py",
        "src/sequence_manager.py",
        "src/retry_policy.py",
        "src/message_validator.py",
        "tests/test_fix_session.py",
        "tests/test_execution_parser.py",
    ],
    "orms": [
        "src/risk_engine.py",
        "src/order_state_machine.py",
        "src/throttle.py",
        "src/order_id_gen.py",
        "src/position_tracker.py",
        "src/sweeper.py",
        "src/notional_check.py",
        "tests/test_risk_engine.py",
        "tests/test_state_machine.py",
    ],
    "trade-listener": [
        "src/trade_listener.py",
        "src/deduplicator.py",
        "src/enricher.py",
        "src/fanout.py",
        "src/pnl_calculator.py",
        "src/gap_detector.py",
        "src/consumer_registry.py",
        "tests/test_deduplicator.py",
        "tests/test_pnl_calculator.py",
    ],
    "strategy-interface": [
        "src/strategy_manager.py",
        "src/signal_bridge.py",
        "src/position_sizer.py",
        "src/config_reloader.py",
        "src/state_snapshot.py",
        "src/heartbeat.py",
        "src/order_intent.py",
        "tests/test_strategy_manager.py",
        "tests/test_position_sizer.py",
    ],
}

INSTRUMENT_SUBS: dict[str, str] = {
    "public-feed-listener": "NIFTY50",
    "exchange-adapter": "BANKNIFTY",
    "orms": "RELIANCE",
    "trade-listener": "INFY",
    "strategy-interface": "TCS",
}


def _message_pool(component_name: str) -> list[str]:
    return COMMIT_MESSAGES[component_name]


def _file_pool(component_name: str) -> list[str]:
    return FILES[component_name]


def _pick_message(rng: random.Random, component_name: str) -> str:
    message = rng.choice(_message_pool(component_name))
    subs = {"{instrument}": INSTRUMENT_SUBS[component_name], "{strategy}": "momentum_v1"}
    for key, value in subs.items():
        message = message.replace(key, value)
    return message


def _file_content(repo: str, path: str, counter: int, message: str) -> str:
    return (
        f'"""Module: {path} (generated for {repo})."""\n\n'
        f'# {message}\n\n'
        f"GENERATION_COUNTER = {counter}\n\n"
        f"def run():\n    return {counter}\n"
    )


def _assign_branches(commits: list[dict], handles: list[str], rng: random.Random) -> None:
    topics = ["seq-gap", "session-recovery", "risk-limit", "reconciliation", "config-reload"]
    i = 0
    while i < len(commits):
        if not commits[i]["is_release"] and rng.random() < 0.18 and i + 2 < len(commits):
            branch = f"feature/{handles[i % len(handles)]}-{topics[i % len(topics)]}"
            for _ in range(min(rng.randint(2, 3), len(commits) - i)):
                commits[i]["branch"] = branch
                i += 1
        else:
            i += 1


def _release_entry(version: str, date: datetime, message: str) -> str:
    return f"- **v{version}** ({date.strftime('%Y-%m-%d')}): {message}"


def _build_fast_import(repo_name: str, commits: list[dict]) -> tuple[str, dict]:
    lines: list[str] = []
    marks: list[int] = []
    feature_tips: dict[str, int] = {}
    tags: list[tuple[str, int]] = []
    main_mark: int | None = None
    changelog: list[str] = ["# Changelog", ""]

    for idx, commit in enumerate(commits, start=1):
        mark = idx
        marks.append(mark)
        author = commit["author"]
        email = f"{github_handle(author)}@orgbot.dev"
        ts = int(commit["date"].timestamp())
        lines.append(f"commit refs/heads/develop")
        lines.append(f"mark :{mark}")
        lines.append(f"author {author} <{email}> {ts} +0000")
        lines.append(f"committer {author} <{email}> {ts} +0000")
        message_bytes = commit["message"].encode("utf-8")
        lines.append(f"data {len(message_bytes)}")
        lines.append(commit["message"])
        for path, content in commit["files"]:
            data = content.encode("utf-8")
            lines.append(f"M 100644 inline {path}")
            lines.append(f"data {len(data)}")
            lines.append(content)
        if commit["is_release"]:
            version = commit["version"]
            tag_date = commit["date"]
            changelog.append(_release_entry(version, tag_date, commit["message"]))
            lines.append(f"tag v{version}")
            lines.append(f"from :{mark}")
            lines.append(f"tagger {author} <{email}> {ts} +0000")
            tag_msg = f"Release v{version}"
            tag_msg_bytes = tag_msg.encode("utf-8")
            lines.append(f"data {len(tag_msg_bytes)}")
            lines.append(tag_msg)
            tags.append((version, mark))
            main_mark = mark
        branch = commit.get("branch")
        if branch and not commit["is_release"]:
            feature_tips[branch] = mark

    if main_mark is not None:
        lines.append("reset refs/heads/main")
        lines.append(f"from :{main_mark}")
    for branch, mark in feature_tips.items():
        lines.append(f"reset refs/heads/{branch}")
        lines.append(f"from :{mark}")
    lines.append("done")
    return "\n".join(lines), {"tags": tags, "feature_tips": feature_tips}


def _run_fast_import(repo_path: Path, stream: str) -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "develop", str(repo_path)], check=True, capture_output=True)
    result = subprocess.run(
        ["git", "-C", str(repo_path), "fast-import", "--quiet"],
        input=stream.encode("utf-8"),
        check=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"fast-import failed: {result.stderr.decode()}")


def _commit_hashes(repo_path: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-list", "--reverse", "develop"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def _tag_hashes(repo_path: Path) -> dict[str, str]:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "tag", "--list", "--format=%(refname:short) %(objectname)"],
        check=True,
        capture_output=True,
        text=True,
    )
    mapping: dict[str, str] = {}
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) == 2:
            mapping[parts[0]] = parts[1]
    return mapping


def _branch_names(repo_path: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "for-each-ref", "--format=%(refname:short)", "refs/heads"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def generate_repo(component: dict, base_dir: Path, seed: int) -> dict:
    rng = make_rng(seed)
    component_name = component["name"]
    repo_name = component["repo"]
    members = component_people(component_name)
    handles = [m["github_handle"] for m in members]
    names = [m["name"] for m in members]
    weights = [1.6 if i == seed % len(members) else 1.0 for i in range(len(members))]

    total = rng.randint(150, 200)
    dates = business_dates(rng, total, FIXED_START, FIXED_END)

    version = "1.0.0"
    release_every = rng.randint(10, 16)
    release_count = 0
    commits: list[dict] = []
    for i in range(total):
        is_release = (i + 1) % release_every == 0 and i > 6
        if is_release:
            release_count += 1
            version = f"1.{release_count}.0"
        author = rng.choices(names, weights=weights, k=1)[0]
        message = _pick_message(rng, component_name)
        n_files = rng.randint(1, 3)
        paths = rng.sample(_file_pool(component_name), n_files)
        files = []
        for counter, path in enumerate(paths):
            files.append((path, _file_content(repo_name, path, counter, message)))
        if is_release:
            files.append(("VERSION", f"v{version}\n"))
            files.append(("CHANGELOG.md", f"# Changelog\n\n- **v{version}**: Release snapshot\n"))
        commits.append(
            {
                "author": author,
                "date": dates[i],
                "message": message,
                "files": files,
                "is_release": is_release,
                "version": version if is_release else None,
                "branch": "develop",
            }
        )

    _assign_branches(commits, handles, rng)

    stream, meta = _build_fast_import(repo_name, commits)
    repo_path = base_dir / repo_name
    _run_fast_import(repo_path, stream)

    hashes = _commit_hashes(repo_path)
    if len(hashes) != len(commits):
        raise RuntimeError(
            f"Expected {len(commits)} commits for {repo_name}, got {len(hashes)}"
        )

    tag_hash_map = _tag_hashes(repo_path)
    version_by_mark: dict[int, str] = {}
    for version, mark in meta["tags"]:
        version_by_mark[mark] = version
    mark_hashes = dict(zip(range(1, len(commits) + 1), hashes))

    records = []
    current_tag: str | None = None
    for idx, commit in enumerate(commits, start=1):
        if commit["is_release"]:
            current_tag = commit["version"]
        records.append(
            {
                "hash": mark_hashes[idx],
                "message": commit["message"],
                "author": commit["author"],
                "author_email": f"{github_handle(commit['author'])}@orgbot.dev",
                "date": iso(commit["date"]),
                "branch": commit["branch"],
                "version_tag": current_tag,
                "files": [path for path, _ in commit["files"] if path not in ("VERSION",)],
            }
        )

    tags = []
    for version, mark in meta["tags"]:
        tags.append({"name": version, "commit_hash": mark_hashes[mark]})

    repo_index = {
        "repo": repo_name,
        "component": component_name,
        "current_version": max((t["name"] for t in tags), default="v1.0.0"),
        "commits": records,
        "tags": tags,
        "branches": _branch_names(repo_path),
    }
    return repo_index


def generate(base_dir: Path, seed: int) -> list[dict]:
    indexes = []
    rng = make_rng(seed)
    for component in COMPONENTS:
        repo_seed = rng.randrange(1 << 30)
        indexes.append(generate_repo(component, base_dir, repo_seed))
    return indexes
