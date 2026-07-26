from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "evet"}


def _int_list(value: str | None) -> list[int]:
    if not value or not value.strip():
        return []
    out: list[int] = []
    for part in value.split(","):
        part = part.strip().strip('"').strip("'")
        if not part:
            continue
        # @username kabul edilmez — sadece sayısal Telegram user id
        if not part.lstrip("-").isdigit():
            raise ValueError(
                f"TELEGRAM_ADMIN_IDS geçersiz: {part!r}. "
                "Sadece sayısal user id yaz (örn. 123456789). @username olmaz."
            )
        out.append(int(part))
    return out


def _str_list(value: str | None) -> list[str]:
    if not value or not value.strip():
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    # Otomatik gönderim hedef grup(lar); virgülle birden fazla
    telegram_chat_ids: list[str]
    # Komut kullanabilecek Telegram user id(ler) — zorunlu (Railway env)
    telegram_admin_ids: list[int]
    toniva_base_url: str
    toniva_api_key: str
    timezone: str
    schedule_sabah: str
    schedule_oglen: str
    schedule_aksam: str
    enable_schedule: bool
    mock_mode: bool

    @property
    def has_toniva(self) -> bool:
        key = self.toniva_api_key
        return bool(key) and not key.startswith("tva_xxx") and key != "CHANGE_ME"

    @property
    def primary_chat_id(self) -> str:
        return self.telegram_chat_ids[0] if self.telegram_chat_ids else ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if (
            not self.telegram_bot_token
            or ":" not in self.telegram_bot_token
            or self.telegram_bot_token.startswith("123456")
            or "CHANGE_ME" in self.telegram_bot_token
        ):
            errors.append("TELEGRAM_BOT_TOKEN eksik veya geçersiz (Railway/env).")
        if not self.telegram_admin_ids:
            errors.append(
                "TELEGRAM_ADMIN_IDS zorunlu. Kendi Telegram user id'ni Railway env'e ekle."
            )
        if self.enable_schedule and not self.telegram_chat_ids:
            errors.append(
                "Zamanlayıcı açıkken TELEGRAM_CHAT_ID veya TELEGRAM_CHAT_IDS gerekli."
            )
        if not self.mock_mode and not self.has_toniva:
            errors.append("TONIVA_API_KEY eksik. Deneme için MOCK_MODE=true kullanın.")
        return errors


def load_settings() -> Settings:
    # TELEGRAM_CHAT_IDS (çoklu) veya TELEGRAM_CHAT_ID (tekil)
    chat_ids = _str_list(os.getenv("TELEGRAM_CHAT_IDS"))
    if not chat_ids:
        single = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if single:
            chat_ids = [single]

    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_ids=chat_ids,
        telegram_admin_ids=_int_list(os.getenv("TELEGRAM_ADMIN_IDS")),
        toniva_base_url=os.getenv(
            "TONIVA_BASE_URL", "https://crm.toniva.net/api/public/v1"
        ).rstrip("/"),
        toniva_api_key=os.getenv("TONIVA_API_KEY", "").strip(),
        timezone=os.getenv("TIMEZONE", "Europe/Istanbul").strip() or "Europe/Istanbul",
        schedule_sabah=os.getenv("SCHEDULE_SABAH", "09:00").strip() or "09:00",
        schedule_oglen=os.getenv("SCHEDULE_OGLEN", "13:00").strip() or "13:00",
        schedule_aksam=os.getenv("SCHEDULE_AKSAM", "18:00").strip() or "18:00",
        enable_schedule=_bool(os.getenv("ENABLE_SCHEDULE"), True),
        mock_mode=_bool(os.getenv("MOCK_MODE"), False),
    )
