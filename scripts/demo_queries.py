from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.api.deps import init_state

DEMO_QUERIES = [
    "Who should I contact about a FIX session disconnect?",
    "What caused the P1 incident on the feed listener last month?",
    "What risk limits does ORMS enforce?",
    "Which instruments have had the most trading incidents?",
    "What changed in the trade listener in the last 3 releases?",
    "How does the strategy interface translate signals into orders?",
    "Which team owns the exchange adapter?",
    "How are FIX session disconnects handled?",
]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run representative queries through the OrgBot pipeline")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    args = parser.parse_args(argv)

    state = init_state(args.config)
    for question in DEMO_QUERIES:
        result = state.pipeline.answer(question)
        confidence = result.get("confidence") or {}
        print("=" * 72)
        print(f"Q: {question}")
        print(f"Confidence: {float(confidence.get('score', 0.0)):.2f}")
        print(f"A: {result.get('answer', '')}")
        print("Sources:")
        for source in result.get("sources", [])[:5]:
            print(f"  - {source.get('origin')} ({source.get('kind')})")


if __name__ == "__main__":
    main()
