from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote
from urllib.request import urlopen


@dataclass(slots=True)
class WeatherReport:
    city: str
    temperature_c: float | None
    feels_like_c: float | None
    description: str
    wind_kph: float | None
    humidity: int | None

    def to_turkish_text(self) -> str:
        parcalar = [f"{self.city} için hava durumu: {self.description}."]
        if self.temperature_c is not None:
            parcalar.append(f"Sıcaklık {self.temperature_c:.0f}°C.")
        if self.feels_like_c is not None:
            parcalar.append(f"Hissedilen {self.feels_like_c:.0f}°C.")
        if self.wind_kph is not None:
            parcalar.append(f"Rüzgar {self.wind_kph:.0f} km/sa.")
        if self.humidity is not None:
            parcalar.append(f"Nem %{self.humidity}.")
        return " ".join(parcalar)


class WeatherService:
    def __init__(self, timeout_seconds: int = 10):
        self.timeout_seconds = timeout_seconds

    def get_weather(self, city: str) -> WeatherReport:
        cleaned_city = " ".join(city.split()).strip()
        if not cleaned_city:
            raise ValueError("Şehir adı boş olamaz.")

        encoded_city = quote(cleaned_city)
        url = (
            "https://wttr.in/"
            f"{encoded_city}"
            "?format=j1"
        )

        with urlopen(url, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        current = payload.get("current_condition", [{}])[0]
        weather = payload.get("weather", [{}])[0]

        return WeatherReport(
            city=cleaned_city,
            temperature_c=self._to_float(current.get("temp_C")),
            feels_like_c=self._to_float(current.get("FeelsLikeC")),
            description=self._extract_description(current, weather),
            wind_kph=self._to_float(current.get("windspeedKmph")),
            humidity=self._to_int(current.get("humidity")),
        )

    def get_weather_text(self, city: str) -> str:
        try:
            report = self.get_weather(city)
            return report.to_turkish_text()
        except Exception:
            return f"{city} için hava durumunu şu an alamadım; istersen biraz sonra tekrar bakarım."

    def _extract_description(self, current: dict, weather: dict) -> str:
        descriptions = current.get("weatherDesc") or weather.get("hourly", [{}])[0].get("weatherDesc") or []
        if descriptions and isinstance(descriptions, list):
            first = descriptions[0]
            if isinstance(first, dict):
                value = first.get("value")
                if isinstance(value, str) and value.strip():
                    return value.strip().capitalize()

        if isinstance(current.get("lang_tr"), dict):
            value = current["lang_tr"].get("value")
            if isinstance(value, str) and value.strip():
                return value.strip().capitalize()

        return "Bilinmiyor"

    def _to_float(self, value) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_int(self, value) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None
