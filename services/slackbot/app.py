from __future__ import annotations

import argparse
import logging
import os
import re

from core.config import Config

logger = logging.getLogger(__name__)


def build_app(config_path: str | None = None, client=None):
    """Build a slack-bolt App wired to the transport-independent SlackBot brain."""
    from slack_bolt import App

    from services.api.deps import init_state
    from services.slackbot.bot import SlackBot
    from services.slackbot.client import SlackClientAdapter

    config = Config.load(config_path)

    bot_token = os.environ.get(config.slack_bot_token_env())
    if not bot_token:
        raise RuntimeError(f"Missing Slack bot token; set env var {config.slack_bot_token_env()}")

    state = init_state(config_path)

    live_client = client or SlackClientAdapter(bot_token)
    bot = SlackBot(
        live_client,
        state.pipeline,
        state.feedback_handler,
        thresholds=config.confidence.get("thresholds"),
    )

    app_kwargs = {"token": bot_token, "name": "OrgBot"}
    if not config.slack_socket_mode():
        signing_secret = os.environ.get(config.slack_signing_secret_env())
        if not signing_secret:
            raise RuntimeError(
                f"Events API mode requires {config.slack_signing_secret_env()} to verify requests"
            )
        app_kwargs["signing_secret"] = signing_secret
    app = App(**app_kwargs)

    try:
        auth = app.client.auth_test()
        user_id = (auth.data or {}).get("user_id")
        if user_id:
            bot.set_bot_user_id(user_id)
    except Exception as exc:  # noqa: BLE001 - offline runs should not block startup
        logger.warning("could not resolve bot user id (offline run?): %s", exc)

    @app.event("app_mention")
    def on_app_mention(ack, event, logger):
        ack()
        try:
            bot.handle_mention(event)
        except Exception as exc:  # noqa: BLE001 - keep the listener alive
            logger.error(f"mention handling failed: {exc}")

    @app.action(re.compile(r"^feedback:"))
    def on_block_action(ack, body, logger):
        ack()
        try:
            bot.handle_action(body)
        except Exception as exc:  # noqa: BLE001 - keep the listener alive
            logger.error(f"action handling failed: {exc}")

    @app.view("feedback_correction")
    def on_view_submission(ack, body, logger):
        ack()
        try:
            bot.handle_modal_submission(body)
        except Exception as exc:  # noqa: BLE001 - keep the listener alive
            logger.error(f"view submission handling failed: {exc}")

    return app, bot


def run(config_path: str | None = None) -> None:
    config = Config.load(config_path)
    app, _bot = build_app(config_path)
    if config.slack_socket_mode():
        app_token = os.environ.get(config.slack_app_token_env())
        if not app_token:
            raise RuntimeError(
                f"Socket Mode is enabled but {config.slack_app_token_env()} is missing"
            )
        from slack_bolt.adapter.socket_mode import SocketModeHandler

        SocketModeHandler(app, app_token).start()
    else:
        app.start(port=int(config.api.get("port", 8000)))


def main(argv: list[str] | None = None) -> None:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the OrgBot Slack app")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    args = parser.parse_args(argv)
    run(args.config)


if __name__ == "__main__":
    main()
