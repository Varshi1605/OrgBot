from __future__ import annotations

import argparse
from pathlib import Path

from simulators import doc_simulator, git_simulator, incident_simulator, slack_simulator
from simulators._util import write_json
from simulators.org_ontology import (
    CHANNELS,
    COMPONENTS,
    DEPENDENCIES,
    INSTRUMENTS,
    PEOPLE,
    STRATEGIES,
    TEAMS,
    validate_all,
)


def generate(data_dir: str | Path, seed: int) -> dict:
    validate_all()
    base = Path(data_dir)
    git_dir = base / "git"
    incidents_dir = base / "incidents"
    slack_dir = base / "slack"
    docs_dir = base / "docs"

    git_index = git_simulator.generate(git_dir, seed)
    write_json(base / "git_index.json", git_index)

    incidents = incident_simulator.generate(incidents_dir, git_index, seed)
    slack = slack_simulator.generate(slack_dir, incidents, seed)
    docs = doc_simulator.generate(docs_dir, git_index, seed)

    manifest = {
        "seed": seed,
        "ontology": {
            "people": PEOPLE,
            "components": COMPONENTS,
            "teams": {
                key: {"name": value["name"], "slack_channel": value["slack_channel"]}
                for key, value in TEAMS.items()
            },
            "instruments": INSTRUMENTS,
            "strategies": STRATEGIES,
            "channels": CHANNELS,
            "dependencies": DEPENDENCIES,
        },
        "git": {
            "repos": [
                {
                    "repo": index["repo"],
                    "component": index["component"],
                    "commit_count": len(index["commits"]),
                    "current_version": index["current_version"],
                }
                for index in git_index
            ]
        },
        "incidents": {"count": len(incidents)},
        "slack": {"message_count": len(slack)},
        "docs": docs,
    }
    write_json(base / "manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate OrgBot simulated data")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic seed")
    parser.add_argument("--data-dir", type=str, default="data/simulated")
    args = parser.parse_args(argv)
    manifest = generate(args.data_dir, args.seed)
    print(f"Generated simulated data under {args.data_dir}")
    print(f"Git repos: {len(manifest['git']['repos'])}")
    print(f"Incidents: {manifest['incidents']['count']}")
    print(f"Slack messages: {manifest['slack']['message_count']}")


if __name__ == "__main__":
    main()
