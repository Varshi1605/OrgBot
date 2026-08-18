from __future__ import annotations

from pathlib import Path

from core.connectors.base import BaseConnector, SourceRecord
from simulators._util import read_json

DEFAULT_INCIDENT_FILE = "incidents.json"


class IncidentConnector(BaseConnector):
    source = "incident"

    def _path(self) -> Path:
        return (Path(self.data_dir) if self.data_dir else Path("data/simulated")) / "incidents" / DEFAULT_INCIDENT_FILE

    def fetch(self, cursor: str | None = None) -> list[dict]:
        records = read_json(self._path())
        records.sort(key=lambda r: (r.get("timeline") or {}).get("detected", ""))
        if cursor:
            records = [
                r for r in records if ((r.get("timeline") or {}).get("detected", "") or "") > cursor
            ]
        return records

    def transform(self, raw: dict) -> SourceRecord:
        timeline = raw.get("timeline", {})
        text = (
            f"Incident {raw['id']}: {raw['title']}\n"
            f"Severity: {raw['severity']}\n"
            f"Status: {raw['status']}\n"
            f"Affected components: {', '.join(raw.get('affected_components', []))}\n"
            f"Involved engineers: {', '.join(raw.get('involved_engineers', []))}\n"
            f"Instruments: {', '.join(raw.get('instruments', []))}\n"
            f"Timeline: detected {timeline.get('detected', '')}, acknowledged {timeline.get('acknowledged', '')}, "
            f"mitigated {timeline.get('mitigated', '')}, resolved {timeline.get('resolved', '')}\n"
            f"RCA: {raw.get('rca', '')}\n"
            f"Action items: {'; '.join(raw.get('action_items', []))}"
        )
        detected = timeline.get("detected")
        if detected:
            detected = detected.replace("+00:00", "Z")
        return SourceRecord(
            source=self.source,
            record_id=raw["id"],
            text=text,
            timestamp=detected,
            metadata={
                "id": raw["id"],
                "title": raw["title"],
                "severity": raw["severity"],
                "status": raw["status"],
                "affected_components": raw.get("affected_components", []),
                "involved_engineers": raw.get("involved_engineers", []),
                "instruments": raw.get("instruments", []),
                "timeline": timeline,
                "rca": raw.get("rca", ""),
                "action_items": raw.get("action_items", []),
                "linked_commits": raw.get("linked_commits", {"caused_by": [], "fixed_by": []}),
            },
            cursor=detected or "",
        )
