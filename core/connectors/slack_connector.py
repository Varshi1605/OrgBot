from __future__ import annotations

from pathlib import Path

from core.connectors.base import BaseConnector, SourceRecord
from simulators._util import read_json

DEFAULT_SLACK_FILE = "slack_messages.json"


class SlackConnector(BaseConnector):
    source = "slack"

    def __init__(
        self,
        cursor_store=None,
        data_dir=None,
        live: bool = False,
        channels: list[str] | None = None,
        messages_fetch_limit: int = 100,
        max_pages: int = 10,
        client=None,
    ):
        super().__init__(cursor_store=cursor_store, data_dir=data_dir)
        self.live = live
        self.channels = list(channels or [])
        self.messages_fetch_limit = max(1, int(messages_fetch_limit))
        self.max_pages = max(1, int(max_pages))
        self.client = client

    def _path(self) -> Path:
        return (Path(self.data_dir) if self.data_dir else Path("data/simulated")) / "slack" / DEFAULT_SLACK_FILE

    def _channel_key(self, channel: str) -> str:
        return f"slack:{channel}"

    def fetch(self, cursor: str | None = None) -> list[dict]:
        if self.live:
            return self._fetch_live(cursor)
        return self._fetch_simulated(cursor)

    def _fetch_simulated(self, cursor: str | None = None) -> list[dict]:
        messages = read_json(self._path())
        threads = self._group_threads(messages)
        threads.sort(key=lambda t: t["timestamp"])
        if cursor:
            threads = [t for t in threads if t["timestamp"] > cursor]
        return threads

    def _fetch_live(self, _cursor: str | None = None) -> list[dict]:
        if self.client is None:
            raise RuntimeError("live Slack connector requires a SlackClient")
        threads: list[dict] = []
        for channel in self.channels:
            per_channel_cursor = (
                self.cursor_store.get_cursor(self._channel_key(channel)) if self.cursor_store else None
            )
            channel_threads = self._fetch_channel_threads(channel, per_channel_cursor)
            if channel_threads and self.cursor_store is not None:
                self.cursor_store.set_cursor(self._channel_key(channel), channel_threads[-1]["timestamp"])
            threads.extend(channel_threads)
        threads.sort(key=lambda t: t["timestamp"])
        return threads

    def _fetch_channel_threads(self, channel: str, cursor: str | None = None) -> list[dict]:
        messages: list[dict] = []
        next_cursor = cursor or ""
        pages = 0
        while True:
            page = self.client.fetch_channel_history(channel, cursor=next_cursor, limit=self.messages_fetch_limit)
            page_messages = page.get("messages") or []
            for message in page_messages:
                message["channel"] = channel
                message.setdefault("author", message.get("user") or "unknown")
            messages.extend(self._exclude_bot_messages(page_messages))
            next_cursor = page.get("next_cursor") or ""
            pages += 1
            if not next_cursor or not page_messages or pages >= self.max_pages:
                break
        threads = self._group_threads(messages)
        threads.sort(key=lambda t: t["timestamp"])
        if cursor:
            threads = [t for t in threads if t["timestamp"] > cursor]
        return threads

    @staticmethod
    def _exclude_bot_messages(messages: list[dict]) -> list[dict]:
        return [m for m in messages if not (m.get("bot_id") or m.get("subtype") == "bot_message")]

    def _group_threads(self, messages: list[dict]) -> list[dict]:
        threads: dict[str, list[dict]] = {}
        for message in messages:
            thread_ts = message.get("thread_ts") or message["ts"]
            threads.setdefault(thread_ts, []).append(message)
        grouped = []
        for thread_ts, msgs in threads.items():
            ordered = sorted(msgs, key=lambda m: m["ts"])
            root = ordered[0]
            grouped.append(
                {
                    "channel": root["channel"],
                    "thread_id": thread_ts,
                    "timestamp": root["ts"],
                    "authors": [m["author"] for m in ordered],
                    "messages": ordered,
                    "components": sorted({c for m in ordered for c in m.get("components", [])}),
                    "instruments": sorted({i for m in ordered for i in m.get("instruments", [])}),
                    "incident_refs": sorted({i for m in ordered for i in m.get("incident_refs", [])}),
                    "reactions": [r for m in ordered for r in m.get("reactions", [])],
                }
            )
        return grouped

    def transform(self, raw: dict) -> SourceRecord:
        lines = []
        for message in raw["messages"]:
            mentions = " ".join(f"@{m}" for m in message.get("mentions", []))
            lines.append(f"{message['author']}: {message['text']} {mentions}".strip())
        topic = lines[0] if lines else ""
        text = f"Slack channel #{raw['channel']}:\n" + "\n".join(lines)
        return SourceRecord(
            source=self.source,
            record_id=raw["thread_id"],
            text=text,
            timestamp=raw["timestamp"],
            metadata={
                "channel": raw["channel"],
                "thread_id": raw["thread_id"],
                "authors": raw["authors"],
                "components": raw["components"],
                "instruments": raw["instruments"],
                "incident_refs": raw["incident_refs"],
                "reactions": raw["reactions"],
                "topic": topic[:200],
            },
            cursor=raw["timestamp"],
        )
