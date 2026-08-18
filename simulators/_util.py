from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

UTC = timezone.utc
FIXED_START = datetime(2023, 7, 3, 9, 30, tzinfo=UTC)
FIXED_END = datetime(2025, 6, 27, 17, 0, tzinfo=UTC)
SECONDS_IN_DAY = 86400


def make_rng(seed: int) -> random.Random:
    return random.Random(seed)


def make_faker(seed: int) -> Faker:
    faker = Faker()
    Faker.seed(seed)
    faker.seed_instance(seed)
    return faker


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def iso(ts: datetime) -> str:
    return ts.isoformat()


def _step_day(rng: random.Random) -> timedelta:
    return timedelta(days=rng.choice([1, 1, 1, 2, 1, 3, 1]))


def business_dates(rng: random.Random, count: int, start: datetime, end: datetime) -> list[datetime]:
    span = (end - start).total_seconds() / SECONDS_IN_DAY
    offsets = sorted(rng.sample(range(1, int(span)), count))
    result: list[datetime] = []
    for offset in offsets:
        candidate = start + timedelta(days=offset)
        if candidate.weekday() >= 5:
            candidate = candidate + timedelta(days=7 - candidate.weekday())
        result.append(candidate)
    return result


def pick(rng: random.Random, values: list, weights: list[float] | None = None):
    return rng.choices(values, weights=weights, k=1)[0]
