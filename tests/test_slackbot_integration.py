from __future__ import annotations

import json

from services.slackbot.bot import SlackBot
from services.slackbot.client import FakeSlackClient
from tests.test_feedback_integration import _seed_ordinary_chunk, build_harness


def test_bot_feedback_flow_improves_answer():
    vector_store, handler, pipeline, feedback_store = build_harness()
    _seed_ordinary_chunk(vector_store)

    client = FakeSlackClient()
    bot = SlackBot(client, pipeline, handler)

    event = {
        "type": "app_mention",
        "channel": "C1",
        "ts": "1234.5678",
        "user": "U1",
        "text": "<@U0LAN0Z89> Who owns the FIX session?",
    }
    bot.handle_mention(event)
    assert len(client.posted) == 1
    posted = client.posted[0]
    ts = posted["ts"]

    bot.handle_action(
        {
            "type": "block_actions",
            "actions": [{"action_id": "feedback:incorrect", "value": "Who owns the FIX session?"}],
            "channel": {"id": "C1"},
            "message": {"ts": ts},
            "user": {"id": "U1"},
            "trigger_id": "T1",
        }
    )
    assert len(client.opened_views) == 1
    metadata = json.loads(client.opened_views[0]["private_metadata"])
    assert metadata["original_answer"] != ""

    bot.handle_modal_submission(
        {
            "type": "view_submission",
            "user": {"id": "U1"},
            "view": {
                "callback_id": "feedback_correction",
                "private_metadata": json.dumps(metadata),
                "state": {
                    "values": {
                        "query_input": {"query_input": {"value": "Who owns the FIX session?"}},
                        "answer_input": {
                            "answer_input": {"value": "The Connectivity team owns the FIX session."}
                        },
                    }
                },
            },
        }
    )

    assert any(f["feedback_type"] == "correction" for f in feedback_store.list_feedback())

    after = pipeline.answer("Who owns the FIX session?")
    assert "Connectivity team" in after["answer"]
    assert any("sme_feedback" in source["origin"] for source in after["sources"])
