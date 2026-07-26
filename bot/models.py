from __future__ import annotations

from dataclasses import dataclass
from datetime import time
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

    @property
    def cutoff(self) -> time:
        """Gün başından (00:00) bu saate kadar olan veriler alınır (dahil değil: exact cutoff = bitiş).

        /sabah  → 00:00–12:00
        /oglen  → 00:00–16:00
        /aksam  → 00:00–23:59:59 (tüm gün)
        """
        return {
            Period.SABAH: time(12, 0, 0),
            Period.OGLEN: time(16, 0, 0),
            Period.AKSAM: time(23, 59, 59),
        }[self]

    @property
    def window_label(self) -> str:
        end = self.cutoff
        if end.hour == 23 and end.minute == 59:
            return "00:00 – 23:59"
        return f"00:00 – {end.strftime('%H:%M')}"


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
    window_label: str = ""

    @property
    def call_leader(self) -> AgentStats | None:
        return self.by_calls[0] if self.by_calls else None

    @property
    def talk_leader(self) -> AgentStats | None:
        return self.by_talk[0] if self.by_talk else None
