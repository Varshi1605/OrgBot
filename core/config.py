from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.confidence.scorer import DEFAULT_WEIGHTS

ENV_PREFIX = "ORGBOT_"
ENV_SEPARATOR = "__"

DEFAULTS_DEPTH = 5


def _flatten(d: dict, prefix: str = "") -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for k, v in d.items():
        key = f"{prefix}{ENV_SEPARATOR}{k}" if prefix else k
        if isinstance(v, dict):
            out.extend(_flatten(v, key))
        else:
            out.append((key, v))
    return out


def _apply_env_overrides(cfg: dict) -> None:
    env_map = {k.upper(): v for k, v in os.environ.items()}
    flat = _flatten(cfg)
    for env_name, value in flat:
        env_key = f"{ENV_PREFIX}{env_name.upper()}"
        if env_key in env_map:
            _set_nested(cfg, env_name.split(ENV_SEPARATOR), _coerce(env_map[env_key], value))


def _set_nested(d: dict, keys: list[str], value: Any) -> None:
    node = d
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


def _coerce(raw: str, reference: Any) -> Any:
    if isinstance(reference, bool):
        return raw.lower() in ("1", "true", "yes", "on")
    if isinstance(reference, int):
        return int(raw)
    if isinstance(reference, float):
        return float(raw)
    return raw


DEFAULT_PRIORITY_BONUS = 0.05
DEFAULT_GOLDEN_PRIORITY = "high"
DEFAULT_APPROVAL_MATCH_THRESHOLD = 0.6
DEFAULT_SYNC_INTERVALS: dict[str, int] = {"slack": 15, "git": 60, "incidents": 1440}


@dataclass
class Config:
    stores: dict
    llm: dict
    embedding: dict
    ingestion: dict
    confidence: dict
    api: dict
    paths: dict
    feedback: dict
    sync: dict
    slack: dict
    source: Path

    @classmethod
    def load(cls, path: str | os.PathLike | None = None) -> Config:
        config_path = Path(path) if path else _default_path()
        if not config_path.is_file():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as fh:
            cfg: dict = yaml.safe_load(fh) or {}
        _apply_env_overrides(cfg)
        root = config_path.parent.parent
        if "paths" in cfg:
            for key in ("chroma", "simulated"):
                raw = cfg["paths"].get(key)
                if raw and not os.path.isabs(raw):
                    cfg["paths"][key] = str((root / raw).resolve())
        return cls(
            stores=cfg.get("stores", {}),
            llm=cfg.get("llm", {}),
            embedding=cfg.get("embedding", {}),
            ingestion=cfg.get("ingestion", {}),
            confidence=cfg.get("confidence", {}),
            api=cfg.get("api", {}),
            paths=cfg.get("paths", {}),
            feedback=cfg.get("feedback", {}),
            sync=cfg.get("sync", {}),
            slack=cfg.get("slack", {}),
            source=config_path,
        )

    def weight(self, name: str) -> float:
        return float(self.confidence.get("weights", {}).get(name, 0.0))

    def threshold(self, name: str) -> float:
        return float(self.confidence.get("thresholds", {}).get(name, 0.5))

    def priority_bonus(self) -> float:
        return float(self.feedback.get("priority_bonus", DEFAULT_PRIORITY_BONUS))

    def golden_priority(self) -> str:
        return str(self.feedback.get("golden_priority", DEFAULT_GOLDEN_PRIORITY))

    def approval_match_threshold(self) -> float:
        return float(self.feedback.get("approval_match_threshold", DEFAULT_APPROVAL_MATCH_THRESHOLD))

    def sync_interval(self, source: str) -> int:
        value = self.sync.get(source, {}).get("interval_minutes")
        if value is None:
            return DEFAULT_SYNC_INTERVALS.get(source, 60)
        return int(value)

    def slack_source(self) -> str:
        return str(self.slack.get("source", "simulated"))

    def slack_socket_mode(self) -> bool:
        return bool(self.slack.get("socket_mode", True))

    def slack_bot_token_env(self) -> str:
        return str(self.slack.get("bot_token_env", "SLACK_BOT_TOKEN"))

    def slack_app_token_env(self) -> str:
        return str(self.slack.get("app_token_env", "SLACK_APP_TOKEN"))

    def slack_signing_secret_env(self) -> str:
        return str(self.slack.get("signing_secret_env", "SLACK_SIGNING_SECRET"))

    def slack_channels(self) -> list[str]:
        channels = self.slack.get("channels", [])
        return [str(c) for c in channels] if isinstance(channels, list) else []

    def slack_messages_fetch_limit(self) -> int:
        return max(1, int(self.slack.get("messages_fetch_limit", 100)))

    def calibrated_weights_path(self) -> Path | None:
        raw = self.confidence.get("calibrated_weights_path")
        if not raw:
            return None
        path = Path(raw)
        return path if path.is_absolute() else (self.source.parent.parent / path).resolve()

    def calibrated_weights(self) -> dict | None:
        path = self.calibrated_weights_path()
        if path is None or not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None
        raw = data.get("weights") if isinstance(data, dict) else None
        if not isinstance(raw, dict):
            return None
        names = tuple(DEFAULT_WEIGHTS)
        values: dict[str, float] = {}
        for name in names:
            try:
                value = float(raw.get(name, "invalid"))
            except (TypeError, ValueError):
                return None
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                return None
            values[name] = value
        total = sum(values.values())
        if total <= 0.0:
            return None
        if abs(total - 1.0) > 1e-6:
            values = {name: value / total for name, value in values.items()}
        return values


def _default_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "config.yaml"


def get_config() -> Config:
    return Config.load()
