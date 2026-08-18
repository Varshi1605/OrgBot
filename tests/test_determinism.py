from __future__ import annotations

from pathlib import Path

from simulators import doc_simulator, slack_simulator


def _slack_output(tmpdir, seed: int) -> str:
    path = Path(tmpdir)
    messages = slack_simulator.generate(path / "slack", [], seed)
    (path / "slack_messages.json").write_text(str(messages), encoding="utf-8")
    return (path / "slack_messages.json").read_text(encoding="utf-8")


def _docs_output(tmpdir, seed: int) -> str:
    path = Path(tmpdir)
    git_index = [
        {"component": name, "tags": [{"name": "v1.0.0"}, {"name": "v1.1.0"}]}
        for name in (
            "public-feed-listener",
            "exchange-adapter",
            "orms",
            "trade-listener",
            "strategy-interface",
        )
    ]
    doc_simulator.generate(path / "docs", git_index, seed)
    return "\n".join(
        f.read_text(encoding="utf-8")
        for f in sorted((path / "docs").rglob("*.md"))
    )


def test_slack_generation_is_deterministic(tmp_path):
    first = _slack_output(tmp_path / "a", 42)
    second = _slack_output(tmp_path / "b", 42)
    assert first == second


def test_slack_generation_differs_by_seed(tmp_path):
    first = _slack_output(tmp_path / "a", 42)
    second = _slack_output(tmp_path / "b", 43)
    assert first != second


def test_docs_generation_is_deterministic(tmp_path):
    first = _docs_output(tmp_path / "a", 42)
    second = _docs_output(tmp_path / "b", 42)
    assert first == second
