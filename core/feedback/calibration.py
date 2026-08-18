from __future__ import annotations

import json
from pathlib import Path

from core.confidence.scorer import DEFAULT_WEIGHTS

SIGNAL_NAMES = tuple(DEFAULT_WEIGHTS)

DEFAULT_NEGATIVE_QUERIES = [
    "What color is the trading desk wall?",
    "How do I book a holiday in the London office?",
    "What is the company picnic menu?",
]


def _invert(matrix: list[list[float]]) -> list[list[float]] | None:
    n = len(matrix)
    augmented = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if abs(augmented[r][col]) > 1e-12), None)
        if pivot is None:
            return None
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        scale = augmented[col][col]
        augmented[col] = [value / scale for value in augmented[col]]
        for row in range(n):
            if row == col:
                continue
            factor = augmented[row][col]
            if abs(factor) < 1e-12:
                continue
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[col])
            ]
    return [row[n:] for row in augmented]


def _fit_least_squares(X: list[list[float]], y: list[float]) -> list[float] | None:
    n_rows = len(X)
    if n_rows == 0:
        return None
    k = len(X[0])
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for row, target in zip(X, y):
        for i in range(k):
            xty[i] += row[i] * target
            for j in range(k):
                xtx[i][j] += row[i] * row[j]
    inverse = _invert(xtx)
    if inverse is None:
        return None
    return [sum(inverse[i][j] * xty[j] for j in range(k)) for i in range(k)]


def calibrate_weights(signal_rows: list[dict], targets: list[float]) -> dict | None:
    if not signal_rows or len(signal_rows) != len(targets):
        return None
    X = [[float(row.get(name, 0.0)) for name in SIGNAL_NAMES] for row in signal_rows]
    fitted = _fit_least_squares(X, targets)
    if fitted is None:
        return None
    weights = {name: float(value) for name, value in zip(SIGNAL_NAMES, fitted)}
    clamped = {name: min(1.0, max(0.0, value)) for name, value in weights.items()}
    total = sum(clamped.values())
    if total <= 0.0:
        return None
    if abs(total - 1.0) > 1e-9:
        clamped = {name: value / total for name, value in clamped.items()}
    return clamped


def load_weights(path: str | Path) -> dict | None:
    file_path = Path(path)
    if not file_path.is_file():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    raw = data.get("weights") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return None
    weights = {}
    for name in SIGNAL_NAMES:
        try:
            value = float(raw.get(name, "invalid"))
        except (TypeError, ValueError):
            return None
        if not 0.0 <= value <= 1.0:
            return None
        weights[name] = value
    return weights


def save_weights(path: str | Path, weights: dict, samples: int = 0) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "weights": {name: round(float(weights[name]), 6) for name in SIGNAL_NAMES},
        "samples": int(samples),
    }
    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


class Calibrator:
    def __init__(self, pipeline, store):
        self.pipeline = pipeline
        self.store = store

    def collect_golden_pairs(self) -> list[dict]:
        return [
            record
            for record in self.store.list_feedback()
            if record["feedback_type"] == "correction" and record.get("sme_answer")
        ]

    def _signal_for(self, question: str) -> dict | None:
        try:
            result = self.pipeline.answer(question)
        except Exception:  # noqa: BLE001
            return None
        signals = (result.get("confidence") or {}).get("signals")
        if not isinstance(signals, dict):
            return None
        return {name: float(signals.get(name, 0.0)) for name in SIGNAL_NAMES}

    def calibrate(self) -> dict | None:
        golden = self.collect_golden_pairs()
        if not golden:
            return None
        rows: list[dict] = []
        targets: list[float] = []
        for record in golden:
            signal = self._signal_for(record["query"])
            if signal is None:
                continue
            rows.append(signal)
            targets.append(1.0)
        for question in DEFAULT_NEGATIVE_QUERIES:
            signal = self._signal_for(question)
            if signal is None:
                continue
            rows.append(signal)
            targets.append(0.0)
        weights = calibrate_weights(rows, targets)
        if weights is None:
            return None
        return {"weights": weights, "golden_pairs": len(golden), "samples": len(rows)}

    def save(self, weights: dict, path: str | Path, samples: int = 0) -> Path:
        save_weights(path, weights, samples=samples)
        return Path(path)


def main(argv: list[str] | None = None) -> None:
    import argparse

    from services.api.deps import init_state

    parser = argparse.ArgumentParser(description="Calibrate confidence weights from golden Q&A pairs")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    args = parser.parse_args(argv)
    state = init_state(args.config)
    output = state.config.calibrated_weights_path()
    if output is None:
        raise SystemExit("confidence.calibrated_weights_path is not set in config")
    calibrator = Calibrator(state.pipeline, state.feedback_store)
    result = calibrator.calibrate()
    if result is None:
        raise SystemExit("calibration failed: no golden pairs or degenerate fit")
    path = calibrator.save(result["weights"], output, samples=result["samples"])
    print(f"Calibrated weights written to {path}: {result['weights']}")


if __name__ == "__main__":
    main()
