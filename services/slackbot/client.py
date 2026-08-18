from __future__ import annotations

from typing import Protocol


class SlackClient(Protocol):
    """Transport-agnostic Slack operations used by the bot brain and the live connector."""

    def post_message(
        self,
        channel: str,
        text: str,
        blocks: list | None = None,
        thread_ts: str | None = None,
    ) -> dict:
        ...

    def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: list | None = None,
    ) -> dict:
        ...

    def open_view(self, trigger_id: str, view: dict) -> dict:
        ...

    def fetch_channel_history(
        self,
        channel: str,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        ...


class FakeSlackClient:
    """In-memory Slack client used by offline tests."""

    def __init__(self) -> None:
        self.posted: list[dict] = []
        self.updated: list[dict] = []
        self.opened_views: list[dict] = []
        self.channel_histories: dict[str, list[dict]] = {}
        self.bot_id = "BOT123"

    def post_message(self, channel, text, blocks=None, thread_ts=None):
        record = {
            "channel": channel,
            "text": text,
            "blocks": blocks or [],
            "thread_ts": thread_ts,
            "ts": f"msg-{len(self.posted) + 1}",
        }
        self.posted.append(record)
        return record

    def update_message(self, channel, ts, text, blocks=None):
        record = {"channel": channel, "ts": ts, "text": text, "blocks": blocks or []}
        self.updated.append(record)
        return record

    def open_view(self, trigger_id, view):
        self.opened_views.append(view)
        return {"ok": True, "view": view}

    def fetch_channel_history(self, channel, cursor=None, limit=100):
        messages = list(self.channel_histories.get(channel, []))
        return {"messages": messages, "next_cursor": ""}


class SlackClientAdapter:
    """Live Slack transport backed by the slack_sdk WebClient.

    Imports are confined to this class; the module itself stays importable
    without slack_sdk installed so offline tests never depend on it.
    """

    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token
        self._client = None

    def _web(self):
        if self._client is None:
            from slack_sdk import WebClient

            self._client = WebClient(token=self._bot_token)
        return self._client

    def post_message(self, channel, text, blocks=None, thread_ts=None):
        response = self._web().chat_postMessage(
            channel=channel,
            text=text,
            blocks=blocks,
            thread_ts=thread_ts,
        )
        return response.data

    def update_message(self, channel, ts, text, blocks=None):
        response = self._web().chat_update(channel=channel, ts=ts, text=text, blocks=blocks)
        return response.data

    def open_view(self, trigger_id, view):
        response = self._web().views_open(trigger_id=trigger_id, view=view)
        return response.data

    def fetch_channel_history(self, channel, cursor=None, limit=100):
        params = {"channel": channel, "limit": int(limit)}
        if cursor:
            params["cursor"] = cursor
        response = self._web().conversations_history(**params)
        data = response.data
        return {
            "messages": data.get("messages", []),
            "next_cursor": (data.get("response_metadata") or {}).get("next_cursor", ""),
        }
