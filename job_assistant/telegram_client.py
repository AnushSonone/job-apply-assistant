from __future__ import annotations

from pathlib import Path

import httpx

from . import config


class TelegramClient:
    def __init__(
        self,
        token: str = config.TELEGRAM_BOT_TOKEN,
        chat_id: str = config.TELEGRAM_CHAT_ID,
    ) -> None:
        self.token = token.strip()
        self.chat_id = chat_id.strip()
        self.base = f"https://api.telegram.org/bot{self.token}"

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_message(self, text: str, disable_preview: bool = False) -> None:
        if not self.configured:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self.base}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "disable_web_page_preview": disable_preview,
                },
            )
            resp.raise_for_status()

    def send_document(self, path: Path, caption: str = "") -> None:
        if not self.configured:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")
        with httpx.Client(timeout=60) as client:
            with path.open("rb") as handle:
                resp = client.post(
                    f"{self.base}/sendDocument",
                    data={"chat_id": self.chat_id, "caption": caption[:1024]},
                    files={"document": (path.name, handle)},
                )
            resp.raise_for_status()
