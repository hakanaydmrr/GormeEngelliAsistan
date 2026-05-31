from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote
from urllib.request import Request, urlopen
import requests


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

        first_error = None
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (WeatherClient)"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            first_error = exc
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0 (WeatherClient)"})
                with urlopen(req, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except Exception:
                return self._get_open_meteo_weather(cleaned_city)

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

    def _get_open_meteo_weather(self, city: str) -> WeatherReport:
        geocode_url = (
            "https://geocoding-api.open-meteo.com/v1/search?"
            f"name={quote(city)}&count=1&language=tr&format=json"
        )
        geo_resp = requests.get(
            geocode_url,
            headers={"User-Agent": "Mozilla/5.0 (WeatherClient)"},
            timeout=self.timeout_seconds,
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        results = geo_data.get("results") or []
        if not results:
            raise ValueError("Şehir için konum bulunamadı.")

        location = results[0]
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if latitude is None or longitude is None:
            raise ValueError("Şehir koordinatları alınamadı.")

        forecast_url = (
            "https://api.open-meteo.com/v1/forecast?"
            f"latitude={latitude}&longitude={longitude}&current_weather=true&timezone=Europe%2FBerlin"
        )
        weather_resp = requests.get(
            forecast_url,
            headers={"User-Agent": "Mozilla/5.0 (WeatherClient)"},
            timeout=self.timeout_seconds,
        )
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()
        current = weather_data.get("current_weather") or {}
        temperature = self._to_float(current.get("temperature"))
        wind_kph = self._to_float(current.get("windspeed"))
        humidity = None
        description = self._open_meteo_weather_description(current.get("weathercode"))

        return WeatherReport(
            city=city,
            temperature_c=temperature,
            feels_like_c=None,
            description=description,
            wind_kph=wind_kph,
            humidity=humidity,
        )

    def _open_meteo_weather_description(self, code) -> str:
        mapping = {
            0: "Açık",
            1: "Parçalı bulutlu",
            2: "Parçalı bulutlu",
            3: "Çok bulutlu",
            45: "Sisli",
            48: "Çok sisli",
            51: "Hafif çiseleme",
            53: "Çiseleme",
            55: "Yoğun çiseleme",
            61: "Hafif yağmur",
            63: "Yağmur",
            65: "Yoğun yağmur",
            66: "Dondurucu yağmur",
            67: "Yoğun dondurucu yağmur",
            71: "Hafif kar",
            73: "Kar",
            75: "Yoğun kar",
            80: "Kuvvetli sağanak yağmur",
            81: "Sağanak yağmur",
            82: "Yoğun sağanak yağmur",
            95: "Fırtına",
            96: "Fırtınalı sağanak yağmur",
            99: "Aşırı fırtına",
        }
        if isinstance(code, int):
            return mapping.get(code, "Bilinmeyen")
        try:
            code_int = int(code)
            return mapping.get(code_int, "Bilinmeyen")
        except (TypeError, ValueError):
            return "Bilinmeyen"

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
