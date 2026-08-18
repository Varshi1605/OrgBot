from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    return _NON_ALNUM.sub("", name.lower())


def canonical_key(name: str) -> str:
    return normalize_name(name)


def github_handle(name: str) -> str:
    return normalize_name(name)


def slack_handle(name: str) -> str:
    return normalize_name(name)


def same_identity(a: str, b: str) -> bool:
    return canonical_key(a) == canonical_key(b)
