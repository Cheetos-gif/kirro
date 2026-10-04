"""`python -m whatsapp_bridge` — runs the webhook receiver (ADR-022).

Always-on, like `voice_bridge`'s health server; unlike `allocator_bridge`, which is a one-shot
CronJob, Meta needs a webhook endpoint it can reach at any moment a user messages the business
number.
"""

from __future__ import annotations

import logging

import uvicorn

from whatsapp_bridge.config import WhatsAppBridgeConfig
from whatsapp_bridge.webhook import create_app

logging.basicConfig(level=logging.INFO)


def main() -> None:
    config = WhatsAppBridgeConfig.from_env()
    app = create_app(config)
    uvicorn.run(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
