from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Period(str, Enum):
    SABAH = "sabah"
    OGLEN = "oglen"
    AKSAM = "aksam"

    @property
    def label(self) -> str:
        return {
            Period.SABAH: "Sabah",
            Period.OGLEN: "Öğlen",
            Period.AKSAM: "Akşam",
        }[self]

    @property
    def title(self) -> str:
        return {
            Period.SABAH: "SABAH ATEŞİ",
            Period.OGLEN: "ÖĞLE ZİRVESİ",
            Period.AKSAM: "AKŞAM TACI",
        }[self]


@dataclass
class AgentStats:
    name: str
    call_count: int = 0
    talk_seconds: int = 0

    @property
    def talk_label(self) -> str:
        total = max(0, int(self.talk_seconds))
        hours, rem = divmod(total, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours:
            return f"{hours} sa {minutes:02d} dk"
        if minutes:
            return f"{minutes} dk {seconds:02d} sn"
        return f"{seconds} sn"


@dataclass
class Leaderboard:
    by_calls: list[AgentStats]
    by_talk: list[AgentStats]
    source: str
    period_label: str
    date_label: str

    @property
    def call_leader(self) -> AgentStats | None:
        return self.by_calls[0] if self.by_calls else None

    @property
    def talk_leader(self) -> AgentStats | None:
        return self.by_talk[0] if self.by_talk else None
