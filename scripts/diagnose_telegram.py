"""Telegram token ve bot erişimini hızlı kontrol et.

Kullanım (env yüklü olmalı):
  set TELEGRAM_BOT_TOKEN=...
  python scripts/diagnose_telegram.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    admin = os.getenv("TELEGRAM_ADMIN_IDS", "").strip()
    if not token or ":" not in token:
        print("FAIL: TELEGRAM_BOT_TOKEN yok / geçersiz")
        sys.exit(1)

    base = f"https://api.telegram.org/bot{token}"
    with httpx.Client(timeout=20.0) as client:
        me = client.get(f"{base}/getMe").json()
        print("getMe:", me)
        if not me.get("ok"):
            print("FAIL: token geçersiz veya bot silinmiş")
            sys.exit(1)

        wh = client.get(f"{base}/getWebhookInfo").json()
        print("getWebhookInfo:", wh)
        result = wh.get("result") or {}
        if result.get("url"):
            print(
                "WARN: Webhook tanımlı → polling çalışmayabilir. "
                "Bot açılışta deleteWebhook çağırır; yine de kontrol et."
            )

        updates = client.get(f"{base}/getUpdates", params={"limit": 5}).json()
        print("getUpdates ok:", updates.get("ok"), "count:", len(updates.get("result") or []))
        for u in (updates.get("result") or [])[-3:]:
            msg = u.get("message") or {}
            from_user = msg.get("from") or {}
            print(
                "  update_id=",
                u.get("update_id"),
                " from_id=",
                from_user.get("id"),
                " text=",
                msg.get("text"),
            )

    print("TELEGRAM_ADMIN_IDS env:", admin or "(BOŞ — bot komutlara yanıt vermez / start fail)")
    print("OK: token canlı. Admin id'ni getUpdates'teki from_id ile eşleştir.")


if __name__ == "__main__":
    main()
