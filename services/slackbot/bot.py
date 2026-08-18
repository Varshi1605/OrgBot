from __future__ import annotations

import json
import re
from collections import OrderedDict

MENTION_RE = re.compile(r"<@[A-Z0-9]+>")
MAX_ACTION_VALUE = 1800
DEFAULT_THRESHOLDS = {"low": 0.4, "high": 0.7}


def truncate(text: str, limit: int = MAX_ACTION_VALUE) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def confidence_badge(score: float, thresholds: dict | None = None) -> str:
    """Map a confidence score to its badge using the config thresholds."""
    thresholds = thresholds or DEFAULT_THRESHOLDS
    low = float(thresholds.get("low", 0.4))
    high = float(thresholds.get("high", 0.7))
    if score >= high:
        return "🟢"
    if score >= low:
        return "🟡"
    return "🔴"


def extract_question(text: str) -> str:
    return MENTION_RE.sub("", text or "").strip()


def build_answer_message(result: dict, thresholds: dict | None = None) -> tuple[str, list[dict]]:
    """Build (plain_text, block_kit_blocks) for a threaded bot answer."""
    answer = str(result.get("answer") or "")
    question = str(result.get("question") or "")
    confidence = result.get("confidence") or {}
    score = float(confidence.get("score", 0.0))
    sources = result.get("sources") or []
    badge = confidence_badge(score, thresholds)
    header = f"{badge} Confidence {score:.2f} / 1.0"
    citations = "\n".join(f"• {s['origin']}" for s in sources[:5] if s.get("origin"))
    body = answer if not citations else f"{answer}\n\n*Sources:*\n{citations}"
    markdown = f"{header}\n{body}"
    query_value = truncate(question)
    buttons = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "✅ Correct", "emoji": True},
            "action_id": "feedback:approve",
            "value": query_value,
        },
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "❌ Incorrect", "emoji": True},
            "action_id": "feedback:incorrect",
            "value": query_value,
        },
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "📝 Needs correction", "emoji": True},
            "action_id": "feedback:annotate",
            "value": query_value,
        },
    ]
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": markdown}},
        {"type": "actions", "elements": buttons},
    ]
    return markdown, blocks


def build_correction_modal(query: str, original_answer: str, annotate: bool = False) -> dict:
    return {
        "type": "modal",
        "callback_id": "feedback_correction",
        "title": {
            "type": "plain_text",
            "text": "Add context" if annotate else "Correct the answer",
        },
        "private_metadata": json.dumps(
            {"original_answer": original_answer, "annotate": annotate},
            ensure_ascii=False,
        ),
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "query_input",
                "label": {"type": "plain_text", "text": "Question"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "query_input",
                    "initial_value": query,
                },
            },
            {
                "type": "input",
                "block_id": "answer_input",
                "label": {"type": "plain_text", "text": "Correct answer or additional context"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "answer_input",
                    "multiline": True,
                },
            },
        ],
    }


class AnswerContextStore:
    """Short-lived LRU of bot answers keyed by (channel_id, message_ts)."""

    def __init__(self, capacity: int = 200) -> None:
        self.capacity = max(1, int(capacity))
        self._items: OrderedDict[tuple[str, str], dict] = OrderedDict()

    def put(self, channel: str, ts: str, entry: dict) -> None:
        key = (channel, ts)
        self._items[key] = dict(entry)
        self._items.move_to_end(key)
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)

    def get(self, channel: str, ts: str) -> dict | None:
        key = (channel, ts)
        if key not in self._items:
            return None
        self._items.move_to_end(key)
        return dict(self._items[key])

    def __len__(self) -> int:
        return len(self._items)


def _input_value(values: dict, block_id: str, action_id: str) -> str:
    node = (values.get(block_id) or {}).get(action_id) or {}
    value = node.get("value")
    return value if isinstance(value, str) else ""


class SlackBot:
    """Transport-independent Slack conversation logic.

    Takes a SlackClient protocol instance plus the in-process RAG pipeline and
    feedback handler; never imports slack_sdk or slack_bolt.
    """

    def __init__(self, client, pipeline, feedback_handler, thresholds=None) -> None:
        self.client = client
        self.pipeline = pipeline
        self.feedback_handler = feedback_handler
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.context = AnswerContextStore()
        self.bot_user_id: str | None = None

    def set_bot_user_id(self, bot_user_id: str) -> None:
        self.bot_user_id = bot_user_id

    def _is_bot_message(self, event: dict) -> bool:
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return True
        return bool(self.bot_user_id and event.get("user") == self.bot_user_id)

    def handle_mention(self, event: dict) -> dict | None:
        if self._is_bot_message(event):
            return None
        question = extract_question(event.get("text", ""))
        if not question:
            return None
        result = self.pipeline.answer(question)
        text, blocks = build_answer_message(result, self.thresholds)
        posted = self.client.post_message(
            channel=event["channel"],
            text=text,
            blocks=blocks,
            thread_ts=event.get("ts"),
        )
        ts = posted.get("ts") if posted else None
        if ts:
            self.context.put(
                event["channel"],
                str(ts),
                {"query": question, "answer": result.get("answer", "")},
            )
        return result

    def handle_action(self, payload: dict) -> dict | None:
        actions = payload.get("actions") or []
        if not actions:
            return None
        action = actions[0]
        action_id = action.get("action_id")
        value = truncate(action.get("value") or "")
        channel = (payload.get("channel") or {}).get("id")
        message_ts = (payload.get("message") or {}).get("ts")
        user_id = (payload.get("user") or {}).get("id")
        ctx = self.context.get(channel, message_ts) if channel and message_ts else None
        query = value or ((ctx or {}).get("query", ""))
        original_answer = (ctx or {}).get("answer", "") if ctx else ""

        if action_id == "feedback:approve":
            if not query or not original_answer:
                return None
            return self.feedback_handler.submit(
                {
                    "query": query,
                    "original_answer": original_answer,
                    "sme_answer": "",
                    "feedback_type": "approval",
                    "sme_id": user_id or "unknown",
                }
            )
        if action_id in ("feedback:incorrect", "feedback:annotate"):
            return self.open_correction_modal(
                trigger_id=payload.get("trigger_id"),
                query=query,
                original_answer=original_answer,
                annotate=(action_id == "feedback:annotate"),
            )
        return None

    def open_correction_modal(
        self,
        trigger_id,
        query: str,
        original_answer: str,
        annotate: bool = False,
    ) -> dict | None:
        if not trigger_id:
            return None
        view = build_correction_modal(query, original_answer, annotate)
        self.client.open_view(trigger_id, view)
        return view

    def handle_modal_submission(self, payload: dict) -> dict:
        view = payload.get("view") or {}
        user_id = (payload.get("user") or {}).get("id", "unknown")
        metadata_raw = view.get("private_metadata") or "{}"
        try:
            metadata = json.loads(metadata_raw)
        except (TypeError, ValueError):
            metadata = {}
        values = (view.get("state") or {}).get("values") or {}
        query = _input_value(values, "query_input", "query_input")
        sme_answer = _input_value(values, "answer_input", "answer_input")
        annotate = bool(metadata.get("annotate"))
        return self.feedback_handler.submit(
            {
                "query": query,
                "original_answer": metadata.get("original_answer", ""),
                "sme_answer": sme_answer,
                "feedback_type": "annotation" if annotate else "correction",
                "sme_id": user_id,
            }
        )
