from __future__ import annotations

import argparse
import os

from core.config import Config
from core.sync.scheduler import SyncScheduler

SCHEDULED_SOURCES = ("slack", "git", "incidents")

SYNC_SOURCE_MAP = {
    "slack": "slack",
    "git": "git",
    "incidents": "incident",
}


def run_scheduler(config_path: str | None = None) -> None:
    from ingestion.ingest_all import ingest_source
    from services.api.deps import init_state

    config = Config.load(config_path)
    state = init_state(config_path)

    def sync_source(source: str) -> None:
        if source == "slack" and config.slack_source() == "live" and not os.environ.get(config.slack_bot_token_env()):
            print(
                "[scheduler] slack: live mode configured but "
                f"{config.slack_bot_token_env()} is missing; skipping live Slack"
            )
            return
        stats = ingest_source(
            config,
            SYNC_SOURCE_MAP[source],
            state.ingestion_pipeline,
            state.feedback_store,
            state.ontology,
            incremental=True,
        )
        print(f"[scheduler] {source}: {stats}")

    intervals = {source: config.sync_interval(source) for source in SCHEDULED_SOURCES}
    scheduler = SyncScheduler(sync_source, intervals)
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run scheduled incremental ingestion")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    args = parser.parse_args(argv)
    run_scheduler(args.config)


if __name__ == "__main__":
    main()
