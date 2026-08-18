from __future__ import annotations

from core.connectors.slack_connector import SlackConnector
from core.processing.chunker import Chunker
from services.slackbot.client import FakeSlackClient


class FakeCursorStore:
    def __init__(self):
        self.cursors: dict[str, str] = {}

    def get_cursor(self, source: str) -> str | None:
        return self.cursors.get(source)

    def set_cursor(self, source: str, value: str) -> None:
        self.cursors[source] = value


def _message(ts, thread_ts, author="Rohit Gupta", text="discussion", bot_id=None, subtype=None):
    message = {
        "ts": ts,
        "thread_ts": thread_ts,
        "author": author,
        "text": text,
        "components": [],
        "instruments": [],
    }
    if bot_id:
        message["bot_id"] = bot_id
    if subtype:
        message["subtype"] = subtype
    return message


def _connector(client, channels, store):
    return SlackConnector(
        cursor_store=store,
        live=True,
        channels=channels,
        client=client,
    )


def test_live_sync_fetches_only_allowlisted_channels():
    store = FakeCursorStore()
    client = FakeSlackClient()
    client.channel_histories = {
        "C1": [_message("100.1", "100.1"), _message("100.2", "100.2")],
        "C2": [_message("200.1", "200.1")],
    }
    connector = _connector(client, ["C1"], store)

    results = connector.sync(Chunker())

    assert len(results) == 2
    assert store.get_cursor("slack:C1") == "100.2"
    assert store.get_cursor("slack:C2") is None
    assert store.get_cursor("slack") == "100.2"


def test_live_sync_excludes_bot_id_messages():
    store = FakeCursorStore()
    client = FakeSlackClient()
    client.channel_histories = {
        "C1": [
            _message("100.1", "100.1", bot_id="BOT123", text="bot reply"),
            _message("100.2", "100.2", text="human question"),
        ]
    }
    connector = _connector(client, ["C1"], store)

    results = connector.sync(Chunker())

    assert len(results) == 1
    record = results[0][0]
    assert record.record_id == "100.2"
    assert "bot reply" not in record.text


def test_live_sync_excludes_bot_message_subtype():
    store = FakeCursorStore()
    client = FakeSlackClient()
    client.channel_histories = {
        "C1": [
            _message("100.1", "100.1", subtype="bot_message", text="automated"),
            _message("100.2", "100.2", text="human"),
        ]
    }
    connector = _connector(client, ["C1"], store)

    results = connector.sync(Chunker())

    assert len(results) == 1
    assert results[0][0].record_id == "100.2"


def test_live_sync_per_channel_cursor_advances_and_resumes():
    store = FakeCursorStore()
    client = FakeSlackClient()
    client.channel_histories["C1"] = [_message("100.1", "100.1"), _message("100.2", "100.2")]
    connector = _connector(client, ["C1"], store)

    first = connector.sync(Chunker())
    assert len(first) == 2
    assert store.get_cursor("slack:C1") == "100.2"

    second = connector.sync(Chunker())
    assert second == []

    client.channel_histories["C1"].append(_message("100.3", "100.3"))
    third = connector.sync(Chunker())
    assert len(third) == 1
    assert third[0][0].record_id == "100.3"
    assert store.get_cursor("slack:C1") == "100.3"
    assert store.get_cursor("slack") == "100.3"


def test_live_sync_tracks_separate_cursors_per_channel():
    store = FakeCursorStore()
    client = FakeSlackClient()
    client.channel_histories = {
        "C1": [_message("100.1", "100.1")],
        "C2": [_message("200.1", "200.1")],
    }
    connector = _connector(client, ["C1", "C2"], store)

    connector.sync(Chunker())

    assert store.get_cursor("slack:C1") == "100.1"
    assert store.get_cursor("slack:C2") == "200.1"
    assert store.get_cursor("slack") == "200.1"


def test_live_sync_groups_threads_and_reuses_transform():
    store = FakeCursorStore()
    client = FakeSlackClient()
    client.channel_histories = {
        "C1": [
            _message("100.1", "100.1", text="root"),
            _message("100.2", "100.1", author="Vikram Das", text="reply"),
        ]
    }
    connector = _connector(client, ["C1"], store)

    results = connector.sync(Chunker())

    assert len(results) == 1
    record = results[0][0]
    assert record.record_id == "100.1"
    assert record.metadata["authors"] == ["Rohit Gupta", "Vikram Das"]
    assert "reply" in record.text
