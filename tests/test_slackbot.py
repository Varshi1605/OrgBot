from __future__ import annotations

import json

from services.slackbot.bot import (
    AnswerContextStore,
    SlackBot,
    build_answer_message,
    confidence_badge,
    extract_question,
)
from services.slackbot.client import FakeSlackClient


class FakePipeline:
    def __init__(self, result=None):
        self.result = result or {
            "question": "Who owns the FIX session?",
            "answer": "The Connectivity team owns the FIX session.",
            "confidence": {
                "score": 0.8,
                "signals": {},
                "low_confidence": False,
                "high_confidence": True,
                "threshold": 0.5,
            },
            "sources": [
                {"origin": "git:abc:0", "kind": "vector", "excerpt": "FIX session fix", "score": 0.9}
            ],
            "graph_path": [],
        }
        self.questions: list[str] = []

    def answer(self, question):
        self.questions.append(question)
        return dict(self.result)


class FakeFeedbackHandler:
    def __init__(self):
        self.submissions: list[dict] = []

    def submit(self, payload):
        record = {"id": len(self.submissions) + 1, **payload}
        self.submissions.append(record)
        return record


def _mention_event(channel="C1", ts="1234.5678", user="U1", text="<@U0LAN0Z89> Who owns the FIX session?"):
    return {"type": "app_mention", "channel": channel, "ts": ts, "user": user, "text": text}


def _button_payload(action_id, value="Who owns the FIX session?", ts="msg-1", user="U1", trigger="T1"):
    return {
        "type": "block_actions",
        "actions": [{"action_id": action_id, "value": value}],
        "channel": {"id": "C1"},
        "message": {"ts": ts},
        "user": {"id": user},
        "trigger_id": trigger,
    }


def test_confidence_badge_high():
    assert confidence_badge(0.9) == "🟢"
    assert confidence_badge(0.7) == "🟢"


def test_confidence_badge_medium():
    assert confidence_badge(0.6) == "🟡"
    assert confidence_badge(0.4) == "🟡"


def test_confidence_badge_low():
    assert confidence_badge(0.39) == "🔴"
    assert confidence_badge(0.0) == "🔴"


def test_extract_question_strips_mention():
    assert extract_question("<@U0LAN0Z89> Who owns the FIX session?") == "Who owns the FIX session?"
    assert extract_question("<@BOT123>") == ""


def test_build_answer_message_contains_answer_citations_and_buttons():
    text, blocks = build_answer_message(FakePipeline().result)
    assert "The Connectivity team owns the FIX session." in text
    assert "git:abc:0" in text
    assert "🟢" in text
    action_blocks = [b for b in blocks if b["type"] == "actions"]
    assert len(action_blocks) == 1
    action_ids = [el["action_id"] for el in action_blocks[0]["elements"]]
    assert action_ids == ["feedback:approve", "feedback:incorrect", "feedback:annotate"]
    assert all(el["value"] == "Who owns the FIX session?" for el in action_blocks[0]["elements"])


def test_mention_posts_threaded_reply_with_answer_citations_and_buttons():
    client = FakeSlackClient()
    pipeline = FakePipeline()
    bot = SlackBot(client, pipeline, FakeFeedbackHandler())
    bot.handle_mention(_mention_event())

    assert pipeline.questions == ["Who owns the FIX session?"]
    assert len(client.posted) == 1
    post = client.posted[0]
    assert post["channel"] == "C1"
    assert post["thread_ts"] == "1234.5678"
    assert "The Connectivity team owns the FIX session." in post["text"]
    assert "git:abc:0" in post["text"]
    action_ids = [
        el["action_id"] for b in post["blocks"] if b["type"] == "actions" for el in b["elements"]
    ]
    assert action_ids == ["feedback:approve", "feedback:incorrect", "feedback:annotate"]


def test_approve_button_records_approval():
    client = FakeSlackClient()
    handler = FakeFeedbackHandler()
    bot = SlackBot(client, FakePipeline(), handler)
    bot.handle_mention(_mention_event())
    ts = client.posted[0]["ts"]

    bot.handle_action(_button_payload("feedback:approve", ts=ts))

    assert len(handler.submissions) == 1
    submission = handler.submissions[0]
    assert submission["feedback_type"] == "approval"
    assert submission["query"] == "Who owns the FIX session?"
    assert submission["original_answer"] == "The Connectivity team owns the FIX session."
    assert submission["sme_id"] == "U1"


def test_incorrect_button_opens_correction_modal():
    client = FakeSlackClient()
    bot = SlackBot(client, FakePipeline(), FakeFeedbackHandler())
    bot.handle_mention(_mention_event())
    ts = client.posted[0]["ts"]

    bot.handle_action(_button_payload("feedback:incorrect", ts=ts))

    assert len(client.opened_views) == 1
    view = client.opened_views[0]
    assert view["callback_id"] == "feedback_correction"
    assert view["blocks"][0]["block_id"] == "query_input"
    metadata = json.loads(view["private_metadata"])
    assert metadata["original_answer"] == "The Connectivity team owns the FIX session."
    assert metadata["annotate"] is False


def test_annotate_button_opens_annotation_modal():
    client = FakeSlackClient()
    bot = SlackBot(client, FakePipeline(), FakeFeedbackHandler())
    bot.handle_mention(_mention_event())
    ts = client.posted[0]["ts"]

    bot.handle_action(_button_payload("feedback:annotate", ts=ts))

    assert len(client.opened_views) == 1
    metadata = json.loads(client.opened_views[0]["private_metadata"])
    assert metadata["annotate"] is True


def test_action_without_context_uses_truncated_query_fallback():
    client = FakeSlackClient()
    bot = SlackBot(client, FakePipeline(), FakeFeedbackHandler())

    bot.handle_action(_button_payload("feedback:annotate", value="Who owns the FIX session?", ts="999.9"))

    assert len(client.opened_views) == 1
    query_block = client.opened_views[0]["blocks"][0]
    assert query_block["element"]["initial_value"] == "Who owns the FIX session?"


def test_modal_submission_creates_correction():
    client = FakeSlackClient()
    handler = FakeFeedbackHandler()
    bot = SlackBot(client, FakePipeline(), handler)
    bot.handle_mention(_mention_event())
    ts = client.posted[0]["ts"]
    bot.handle_action(_button_payload("feedback:incorrect", ts=ts))
    view = client.opened_views[0]

    payload = {
        "type": "view_submission",
        "user": {"id": "U42"},
        "view": {
            "callback_id": "feedback_correction",
            "private_metadata": view["private_metadata"],
            "state": {
                "values": {
                    "query_input": {"query_input": {"value": "Who owns the FIX session?"}},
                    "answer_input": {"answer_input": {"value": "The Connectivity team owns the FIX session."}},
                }
            },
        },
    }
    record = bot.handle_modal_submission(payload)

    assert record["feedback_type"] == "correction"
    assert record["sme_id"] == "U42"
    assert record["sme_answer"] == "The Connectivity team owns the FIX session."
    assert handler.submissions[-1]["feedback_type"] == "correction"


def test_modal_submission_creates_annotation():
    client = FakeSlackClient()
    handler = FakeFeedbackHandler()
    bot = SlackBot(client, FakePipeline(), handler)
    bot.handle_mention(_mention_event())
    ts = client.posted[0]["ts"]
    bot.handle_action(_button_payload("feedback:annotate", ts=ts))
    view = client.opened_views[0]

    payload = {
        "type": "view_submission",
        "user": {"id": "U42"},
        "view": {
            "callback_id": "feedback_correction",
            "private_metadata": view["private_metadata"],
            "state": {
                "values": {
                    "query_input": {"query_input": {"value": "What is the deploy process?"}},
                    "answer_input": {"answer_input": {"value": "Deploys run every Friday."}},
                }
            },
        },
    }
    record = bot.handle_modal_submission(payload)

    assert record["feedback_type"] == "annotation"
    assert handler.submissions[-1]["feedback_type"] == "annotation"


def test_bot_ignores_own_messages():
    client = FakeSlackClient()
    bot = SlackBot(client, FakePipeline(), FakeFeedbackHandler())

    bot.handle_mention({**_mention_event(text="<@BOT123> what?"), "bot_id": "BOT123"})
    bot.handle_mention({**_mention_event(ts="2.0"), "subtype": "bot_message"})

    assert client.posted == []


def test_answer_context_lru_evicts_oldest():
    store = AnswerContextStore(capacity=2)
    store.put("C1", "1", {"query": "q1", "answer": "a1"})
    store.put("C1", "2", {"query": "q2", "answer": "a2"})
    store.put("C1", "3", {"query": "q3", "answer": "a3"})
    assert store.get("C1", "1") is None
    assert store.get("C1", "3") == {"query": "q3", "answer": "a3"}
