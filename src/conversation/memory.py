from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class AssistantProfileStore:
    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else Path(__file__).with_name("profile.json")
        self.profile = self._load_profile()

    def _default_profile(self) -> dict[str, str]:
        return {
            "preferred_name": "Hakan",
            "city": "Istanbul",
        }

    def _load_profile(self) -> dict[str, str]:
        if not self.storage_path.exists():
            return self._default_profile()

        try:
            with self.storage_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            return self._default_profile()

        profile = self._default_profile()
        if isinstance(data, dict):
            preferred_name = data.get("preferred_name")
            city = data.get("city")

            if isinstance(preferred_name, str) and preferred_name.strip():
                profile["preferred_name"] = preferred_name.strip()

            if isinstance(city, str) and city.strip():
                profile["city"] = city.strip()

        return profile

    def _save_profile(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("w", encoding="utf-8") as file:
            json.dump(self.profile, file, ensure_ascii=False, indent=2)

    def get_preferred_name(self) -> str:
        return self.profile.get("preferred_name", "Hakan")

    def set_preferred_name(self, name: str) -> str:
        temiz_isim = self._normalize_value(name)
        if temiz_isim:
            self.profile["preferred_name"] = temiz_isim
            self._save_profile()
        return self.get_preferred_name()

    def get_city(self) -> str:
        return self.profile.get("city", "Istanbul")

    def set_city(self, city: str) -> str:
        temiz_sehir = self._normalize_value(city)
        if temiz_sehir:
            self.profile["city"] = temiz_sehir
            self._save_profile()
        return self.get_city()

    def update_from_text(self, text: str) -> dict[str, Any]:
        temiz_metin = " ".join(text.lower().split())
        result: dict[str, Any] = {
            "name_changed": False,
            "city_changed": False,
            "preferred_name": self.get_preferred_name(),
            "city": self.get_city(),
        }

        yeni_isim = self.extract_preferred_name(temiz_metin)
        if yeni_isim:
            result["preferred_name"] = self.set_preferred_name(yeni_isim)
            result["name_changed"] = True

        yeni_sehir = self.extract_city(temiz_metin)
        if yeni_sehir:
            result["city"] = self.set_city(yeni_sehir)
            result["city_changed"] = True

        return result

    def extract_preferred_name(self, text: str) -> str | None:
        patterns = [
            r"bana\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+diye\s+seslen",
            r"beni\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})\s+diye\s+çağır",
            r"adım\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})",
            r"ismim\s+([a-zA-ZçğıöşüÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ0-9\s\-]{1,30})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                aday = self._normalize_value(match.group(1))
                if aday and not self._looks_like_question(aday):
                    return aday

        return None

    def extract_city(self, text: str) -> str | None:
        patterns = [
            r"(?:şehir|sehir|konum|bulunduğum yer|bulundugum yer)\s*[:=]?\s*([a-zA-ZçğıöşüÇĞİÖŞÜ\s\-]{2,40})",
            r"hava durumu\s+(?:için|bak\s*|\s*)?([a-zA-ZçğıöşüÇĞİÖŞÜ\s\-]{2,40})",
            r"([a-zA-ZçğıöşüÇĞİÖŞÜ\s\-]{2,40})\s+hava durumu",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                aday = self._normalize_value(match.group(1))
                if aday and len(aday) >= 2 and not self._looks_like_question(aday):
                    return aday

        return None

    def describe(self) -> str:
        return (
            f"Kullanıcı adı: {self.get_preferred_name()}, "
            f"varsayılan şehir: {self.get_city()}"
        )

    def _normalize_value(self, value: str) -> str:
        temiz = " ".join(value.split()).strip(" .,!?:;\"'")
        if not temiz:
            return ""

        parcalar = temiz.split()
        if parcalar and parcalar[0] in {"benim", "adım", "ismim", "bana", "beni"}:
            temiz = " ".join(parcalar[1:]).strip()

        if len(temiz) > 1:
            return temiz[:1].upper() + temiz[1:]
        return temiz.upper()

    def _looks_like_question(self, value: str) -> bool:
        soru_kelimeleri = {
            "ne",
            "nasıl",
            "nasil",
            "neden",
            "nerede",
            "kim",
            "hangi",
            "mı",
            "mi",
            "mu",
            "mü",
        }
        kelimeler = {kelime.lower() for kelime in value.split()}
        return bool(kelimeler & soru_kelimeleri)
