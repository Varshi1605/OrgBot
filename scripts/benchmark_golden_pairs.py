from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.api.deps import init_state

# Golden Q&A pairs sourced from the simulated corpus. Correctness is measured by
# whether the generated answer contains the expected key phrase (case-insensitive).
GOLDEN_PAIRS: list[tuple[str, str]] = [
    ("Which component manages FIX sessions with the exchange?", "exchange-adapter"),
    ("Which component receives the raw NSE market data broadcast?", "public-feed-listener"),
    ("Which component enforces pre-trade risk limits and order lifecycle?", "orms"),
    ("Which component receives confirmed trade fills from ORMS?", "trade-listener"),
    ("Which component translates strategy signals into orders?", "strategy-interface"),
    ("Which team owns the exchange adapter?", "connectivity"),
    ("Which team owns the ORMS?", "risk & order"),
    ("What limits the rate of order submission per instrument?", "throttle"),
    ("How does ORMS protect against gross exposure breaches?", "gross exposure"),
    ("What detects UDP sequence gaps in the market depth handler?", "sequence gap"),
    ("What handles FIX session recovery after a TCP disconnect?", "session recovery"),
    ("What resets FIX sequence numbers when logon is rejected?", "sequence reset"),
    ("What monitors exchange broadcast restarts?", "restart"),
    ("What handles trade deduplication when fills arrive out of order?", "deduplication"),
    ("What fixes PnL calculation for multi-leg trades?", "multi-leg"),
    ("Which strategy monitors are reporting heartbeat misses?", "heartbeat"),
    ("Which strategy has a signal rate limiter?", "rate limiting"),
    ("What publishes feed status heartbeats?", "heartbeat"),
    ("What color is the trading desk wall?", "green"),
    ("What is the company picnic menu in the canteen?", "biryani"),
]

TARGET_CORRELATION = 0.7


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n != len(ys) or n == 0:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0.0 or var_y == 0.0:
        return 0.0
    return cov / ((var_x * var_y) ** 0.5)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark confidence-vs-correctness correlation on 20 golden Q&A pairs"
    )
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    args = parser.parse_args(argv)

    state = init_state(args.config)
    scores: list[float] = []
    correctness: list[float] = []
    print(f"Running {len(GOLDEN_PAIRS)} golden Q&A pairs...")
    for question, expected in GOLDEN_PAIRS:
        result = state.pipeline.answer(question)
        answer = (result.get("answer") or "").lower()
        score = float((result.get("confidence") or {}).get("score", 0.0))
        correct = 1.0 if expected.lower() in answer else 0.0
        scores.append(score)
        correctness.append(correct)
        print(f"  {'PASS' if correct else 'FAIL'}  {score:.2f}  {question}")

    correlation = pearson(scores, correctness)
    print("-" * 72)
    print(f"Pearson correlation (confidence vs correctness): {correlation:.3f}")
    print(f"Target: > {TARGET_CORRELATION} correlation")
    if correlation > TARGET_CORRELATION:
        print("BENCHMARK PASSED")
    else:
        print("BENCHMARK BELOW TARGET - consider recalibrating confidence weights")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
