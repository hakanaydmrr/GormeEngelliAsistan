from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Literal, Optional

IntentName = Literal[
    "name_change",
    "weather",
    "greeting",
    "small_talk",
    "vision",
    "internet_search",  
    "unknown",
]

@dataclass(slots=True)
class IntentRoute:
    intent: IntentName
    cleaned_text: str
    confidence: float = 1.0
    target: Optional[str] = None

class IntentRouter:
    WEATHER_KEYWORDS = {"hava", "yağmur", "yagm", "sıcaklık", "sicaklik", "rüzgar", "kar", "meteoroloji", "güneş"}
    NAME_CHANGE_PATTERNS = (
        r"bana\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+diye\s+seslen",
        r"beni\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+diye\s+çağır",
        r"artık\s+bana\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+de",
    )
    GREETING_KEYWORDS = {"selam", "merhaba", "günaydın", "iyi akşamlar", "iyi geceler", "nasılsın", "naber"}

    def __init__(self, spatial_store=None):
        self.spatial_store = spatial_store
        self.spatial_targets = self._build_spatial_target_map(spatial_store)
    
    # 🔥 GÖRSEL VE NAVİGASYONEL ŞABLONLAR 🔥
    VISUAL_PATTERNS = (
        r"ne\s+(?:var|gör|gor|görüyon|goruyon)", r"betimle", r"tarif", r"anlat",
        r"neredeyim", r"neresi", r"hangi\s+oda", r"bulunduğum", r"bulundugum", r"karşımda", r"karsimda",
        r"nasıl\s+giderim", r"götür", r"gotur", r"yönlendir", r"yonlendir", r"engel", r"tehlike",
        r"oku", r"yazıyor", r"metin", r"görüyor\s+musun", r"bana\s+bak", r"gitmek\s+istiyorum", r"konumu", r"\bgit\b"
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
            # görsel niyet yüksek; aynı zamanda hedef çıkarımı yap
            target = self._extract_target(cleaned)
            conf = 0.99
            if target:
                conf = min(1.0, conf + 0.03)
            return IntentRoute(intent="vision", cleaned_text=cleaned, confidence=conf, target=target)

        if self._matches_weather(cleaned):
            return IntentRoute(intent="weather", cleaned_text=cleaned, confidence=0.96)
            
        if self._matches_greeting(cleaned):
            return IntentRoute(intent="greeting", cleaned_text=cleaned, confidence=0.90)
        
        if self._matches_search(cleaned):
            return IntentRoute(intent="internet_search", cleaned_text=cleaned, confidence=0.95)

        if cleaned:
            return IntentRoute(intent="small_talk", cleaned_text=cleaned, confidence=0.70)

        return IntentRoute(intent="unknown", cleaned_text=cleaned, confidence=0.10)

    # Basit hedef çıkarımı: sıradan kelime eşlemeleri ile odak hedefi bulur
    def _extract_target(self, text: str) -> Optional[str]:
        cleaned = self._normalize(text)

        target_phrases = [
            ("yatak odası", "Yatak"),
            ("yatak odas", "Yatak"),
            ("yatağa", "Yatak"),
            ("yatakta", "Yatak"),
            ("yatak", "Yatak"),
            ("oturma odası", "Koltuk"),
            ("oturma odas", "Koltuk"),
            ("koltuk", "Koltuk"),
            ("yemek masası", "YemekMasasi"),
            ("yemek masasi", "YemekMasasi"),
            ("yemek masas", "YemekMasasi"),
            ("masaya", "YemekMasasi"),
            ("masa", "YemekMasasi"),
            ("sofra", "YemekMasasi"),
            ("lavabo", "Lavabo"),
            ("lavaboya", "Lavabo"),
            ("tuvalet", "Lavabo"),
            ("banyo", "Lavabo"),
            ("mutfak", "Mutfak"),
            ("buzdolabı", "Buzdolabi"),
            ("buzdolabi", "Buzdolabi"),
            ("fırın", "Firin"),
            ("fırin", "Firin"),
            ("sehp", "Sehpa"),
            ("sehpa", "Sehpa"),
            ("televizyon", "Televizyon"),
            ("tv", "Televizyon"),
            ("kitaplık", "Kitaplik"),
            ("kitaplik", "Kitaplik"),
            ("komodin", "Komodin"),
            ("ayna", "Ayna"),
            ("lamba", "Lamba"),
            ("dolap", "Dolap"),
        ]

        if self.spatial_targets:
            for phrase, target in self.spatial_targets.items():
                if phrase in cleaned:
                    return target

        for phrase, target in target_phrases:
            if phrase in cleaned:
                return target

        # Genel hedef adları için daha geniş eşleme
        generic_match = re.search(r"\b(yatak|koltuk|masa|lavabo|tuvalet|banyo|mutfak|buzdolabı)\b", cleaned)
        if generic_match:
            phrase = generic_match.group(1)
            for key, target in target_phrases:
                if key == phrase:
                    return target
        return None

    def _build_spatial_target_map(self, spatial_store):
        if not spatial_store or not getattr(spatial_store, 'known_rooms', None):
            return {}

        target_map: dict[str, str] = {}
        for room_name, signatures in spatial_store.known_rooms.items():
            if room_name:
                target_map[self._normalize(room_name)] = room_name
            if isinstance(signatures, list):
                for sig in signatures:
                    if not isinstance(sig, str):
                        continue
                    normalized_sig = self._normalize(sig)
                    if normalized_sig and normalized_sig not in target_map:
                        target_map[normalized_sig] = sig.capitalize()
        return target_map

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
