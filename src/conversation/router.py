from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

IntentName = Literal[
    "name_change",
    "weather",
    "greeting",
    "small_talk",
    "vision",
    "unknown",
]


@dataclass(slots=True)
class IntentRoute:
    intent: IntentName
    cleaned_text: str
    confidence: float = 1.0


class IntentRouter:
    WEATHER_KEYWORDS = {
        "hava durumu",
        "hava",
        "yağmur",
        "yagm",
        "sıcaklık",
        "sicaklik",
        "rüzgar",
        "ruzgar",
        "kar",
        "meteoroloji",
    }

    NAME_CHANGE_PATTERNS = (
        r"bana\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+diye\s+seslen",
        r"beni\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+diye\s+çağır",
        r"artık\s+bana\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+de",
        r"adım\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})",
        r"ismim\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})",
    )

    GREETING_KEYWORDS = {
        "selam",
        "merhaba",
        "günaydın",
        "iyi akşamlar",
        "iyi geceler",
        "nasılsın",
        "naber",
    }

    VISUAL_KEYWORDS = {
        "ne var",
        "önümde ne var",
        "ne görüyorum",
        "ne var burada",
        "görüyor musun",
        "okuyor musun",
        "resimde",
        "ekranda",
        "kişi",
        "nesne",
        "metin",
        "yazı",
        "buna bak",
        "bakabilir misin",
    }

    def route(self, text: str) -> IntentRoute:
        cleaned = self._normalize(text)

        if self._matches_name_change(cleaned):
            return IntentRoute(intent="name_change", cleaned_text=cleaned, confidence=0.98)

        if self._matches_weather(cleaned):
            return IntentRoute(intent="weather", cleaned_text=cleaned, confidence=0.96)

        if self._matches_greeting(cleaned):
            return IntentRoute(intent="greeting", cleaned_text=cleaned, confidence=0.90)

        if self._matches_vision(cleaned):
            return IntentRoute(intent="vision", cleaned_text=cleaned, confidence=0.94)

        if cleaned:
            return IntentRoute(intent="small_talk", cleaned_text=cleaned, confidence=0.70)

        return IntentRoute(intent="unknown", cleaned_text=cleaned, confidence=0.10)

    def _normalize(self, text: str) -> str:
        return " ".join(text.lower().split()).strip()

    def _matches_name_change(self, text: str) -> bool:
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.NAME_CHANGE_PATTERNS)

    def _matches_weather(self, text: str) -> bool:
        return any(keyword in text for keyword in self.WEATHER_KEYWORDS) and (
            "hava" in text or "yağ" in text or "yagm" in text or "sıcak" in text or "sicak" in text
        )

    def _matches_greeting(self, text: str) -> bool:
        return any(keyword in text for keyword in self.GREETING_KEYWORDS)

    def _matches_vision(self, text: str) -> bool:
        return any(keyword in text for keyword in self.VISUAL_KEYWORDS)
