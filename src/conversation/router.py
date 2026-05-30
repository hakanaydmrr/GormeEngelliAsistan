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
    "internet_search",  # <--- CANLI İNTERNET ARAMASI İÇİN YENİ NİYET
    "unknown",
]

@dataclass(slots=True)
class IntentRoute:
    intent: IntentName
    cleaned_text: str
    confidence: float = 1.0

class IntentRouter:
    WEATHER_KEYWORDS = {"hava", "yağmur", "yagm", "sıcaklık", "sicaklik", "rüzgar", "kar", "meteoroloji", "güneş"}
    NAME_CHANGE_PATTERNS = (
        r"bana\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+diye\s+seslen",
        r"beni\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+diye\s+çağır",
        r"artık\s+bana\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+de",
    )
    GREETING_KEYWORDS = {"selam", "merhaba", "günaydın", "iyi akşamlar", "iyi geceler", "nasılsın", "naber"}
    
    # 🔥 GÖRSEL VE NAVİGASYONEL ŞABLONLAR 🔥
    VISUAL_PATTERNS = (
        r"ne\s+(?:var|gör|gor|görüyon|goruyon)", r"betimle", r"tarif", r"anlat",
        r"neredeyim", r"neresi", r"hangi\s+oda", r"bulunduğum", r"bulundugum", r"karşımda", r"karsimda",
        r"nasıl\s+giderim", r"götür", r"gotur", r"yönlendir", r"yonlendir", r"engel", r"tehlike",
        r"oku", r"yazıyor", r"metin", r"görüyor\s+musun", r"bana\s+bak", r"gitmek\s+istiyorum", r"konumu"
    )

    SEARCH_PATTERNS = (
        r"kimdir", r"nedir", r"kaçtır", r"kactir", r"ne\s+kadar", r"kim\s+kazandı",
        r"internetten\s+(?:bak|araştır|sorgula)", r"güncel", r"son\s+durum", r"haberleri",
        r"altın", r"dolar", r"döviz", r"borsa", r"maçı", r"skoru", r"tarihte\s+bugün"
    )

    def route(self, text: str) -> IntentRoute:
        cleaned = self._normalize(text)

        if self._matches_name_change(cleaned):
            return IntentRoute(intent="name_change", cleaned_text=cleaned, confidence=0.98)
            
        # Önceliği vizyon katmanına verdik
        if self._matches_vision(cleaned):
            return IntentRoute(intent="vision", cleaned_text=cleaned, confidence=0.99)

        if self._matches_weather(cleaned):
            return IntentRoute(intent="weather", cleaned_text=cleaned, confidence=0.96)
            
        if self._matches_greeting(cleaned):
            return IntentRoute(intent="greeting", cleaned_text=cleaned, confidence=0.90)
        
        if self._matches_search(cleaned):
            return IntentRoute(intent="internet_search", cleaned_text=cleaned, confidence=0.95)

        if cleaned:
            return IntentRoute(intent="small_talk", cleaned_text=cleaned, confidence=0.70)

        return IntentRoute(intent="unknown", cleaned_text=cleaned, confidence=0.10)

    def _normalize(self, text: str) -> str:
        return " ".join(text.lower().split()).strip()

    def _matches_name_change(self, text: str) -> bool:
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.NAME_CHANGE_PATTERNS)
    def _matches_weather(self, text: str) -> bool:
        return any(keyword in text for keyword in self.WEATHER_KEYWORDS)
    def _matches_greeting(self, text: str) -> bool:
        return any(keyword in text for keyword in self.GREETING_KEYWORDS)
    def _matches_vision(self, text: str) -> bool:
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.VISUAL_PATTERNS)
    def _matches_search(self, text: str) -> bool:
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in self.SEARCH_PATTERNS)