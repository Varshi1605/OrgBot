from __future__ import annotations

from pathlib import Path

from core.connectors.base import BaseConnector, SourceRecord
from simulators._util import read_json

DEFAULT_GIT_INDEX = "git_index.json"


class GitConnector(BaseConnector):
    source = "git"

    def __init__(self, cursor_store=None, data_dir: Path | None = None):
        super().__init__(cursor_store=cursor_store, data_dir=data_dir)
        self._records: list[SourceRecord] = []

    def _index_path(self) -> Path:
        return (Path(self.data_dir) if self.data_dir else Path("data/simulated")) / DEFAULT_GIT_INDEX

    def fetch(self, cursor: str | None = None) -> list[dict]:
        index = read_json(self._index_path())
        records = []
        for repo_index in index:
            for commit in repo_index["commits"]:
                records.append(
                    {
                        "repo": repo_index["repo"],
                        "component": repo_index["component"],
                        **commit,
                    }
                )
        records.sort(key=lambda r: r.get("date", ""))
        if cursor:
            records = [r for r in records if (r.get("date", "") or "") > cursor]
        return records

    def transform(self, raw: dict) -> SourceRecord:
        files = ", ".join(raw.get("files", []))
        text = f"[{raw['repo']}] {raw['message']}\nChanged files: {files}"
        return SourceRecord(
            source=self.source,
            record_id=raw["hash"],
            text=text,
            timestamp=raw.get("date"),
            metadata={
                "repo": raw.get("repo"),
                "component": raw.get("component"),
                "author": raw.get("author"),
                "author_email": raw.get("author_email"),
                "branch": raw.get("branch"),
                "version_tag": raw.get("version_tag"),
                "files": raw.get("files", []),
            },
            cursor=raw.get("date", ""),
        )
