from __future__ import annotations

from pathlib import Path

from core.connectors.base import BaseConnector, SourceRecord

DOC_TYPES = {
    "README.md": "README",
    "ARCHITECTURE.md": "ARCHITECTURE",
    "RUNBOOK.md": "RUNBOOK",
    "CHANGELOG.md": "CHANGELOG",
}


class DocsConnector(BaseConnector):
    source = "docs"

    def _docs_root(self) -> Path:
        return (Path(self.data_dir) if self.data_dir else Path("data/simulated")) / "docs"

    def fetch(self, cursor: str | None = None) -> list[dict]:
        root = self._docs_root()
        records = []
        for component_dir in sorted(root.iterdir()):
            if not component_dir.is_dir():
                continue
            component = component_dir.name
            for markdown in sorted(component_dir.glob("*.md")):
                doc_type = DOC_TYPES.get(markdown.name, "OTHER")
                content = markdown.read_text(encoding="utf-8")
                records.append(
                    {
                        "component": component,
                        "path": f"docs/{component}/{markdown.name}",
                        "doc_type": doc_type,
                        "content": content,
                    }
                )
        records.sort(key=lambda r: r["path"])
        if cursor:
            records = [r for r in records if r["path"] > cursor]
        return records

    def transform(self, raw: dict) -> SourceRecord:
        return SourceRecord(
            source=self.source,
            record_id=raw["path"],
            text=raw["content"],
            timestamp=None,
            metadata={
                "component": raw["component"],
                "path": raw["path"],
                "doc_type": raw["doc_type"],
            },
            cursor=raw["path"],
        )
