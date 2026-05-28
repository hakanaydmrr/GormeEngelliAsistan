import json
from pathlib import Path


class SpatialMemoryStore:
    def __init__(self, storage_path: str | Path | None = None):
        # Hafızayı src/conversation/spatial_memory.json olarak kaydedecek
        self.storage_path = (
            Path(storage_path)
            if storage_path
            else Path(__file__).with_name("spatial_memory.json")
        )
        self.known_rooms = self._load_memory()

    def _load_memory(self) -> dict[str, list[str]]:
        """Kayıtlı ev hafızasını diskten yükler."""
        if not self.storage_path.exists():
            return {}
        try:
            with self.storage_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception:
            return {}

        if not isinstance(data, dict):
            return {}

        normalized: dict[str, list[str]] = {}
        for room_name, signatures in data.items():
            temiz_oda = self._normalize_room_name(str(room_name))
            temiz_imzalar = self._normalize_signatures(signatures if isinstance(signatures, list) else [])
            if temiz_oda:
                normalized[temiz_oda] = temiz_imzalar

        return normalized

    def _save_memory(self) -> None:
        """Öğrenilen odaları kalıcı olarak kaydeder."""
        with self.storage_path.open("w", encoding="utf-8") as file:
            json.dump(self.known_rooms, file, ensure_ascii=False, indent=2)

    def oda_imzasi_cikar(self, yolo_nesneleri: list[dict], limit: int = 6) -> list[str]:
        """Karedeki nesnelerden oda imzası olacak kısa bir nesne listesi üretir."""
        if not yolo_nesneleri:
            return []

        sirali_nesneler = sorted(
            yolo_nesneleri,
            key=lambda nesne: float(nesne.get("guven", 0.0)),
            reverse=True,
        )

        imzalar: list[str] = []
        for nesne in sirali_nesneler[:limit]:
            ad = self._normalize_object_name(str(nesne.get("ad", "")))
            if ad and ad not in imzalar:
                imzalar.append(ad)

        return imzalar

    def oda_tahmin_et(self, yolo_nesneleri: list[dict]) -> str | None:
        """YOLO'dan gelen nesneleri kayıtlı oda imzalarıyla eşleştirir."""
        if not yolo_nesneleri:
            return None

        ekrandaki_nesneler = set(self.oda_imzasi_cikar(yolo_nesneleri))
        if not ekrandaki_nesneler:
            return None

        en_iyi_oda = None
        en_iyi_eslesme = 0

        for oda_adi, imza_nesneler in self.known_rooms.items():
            eslesen = len(ekrandaki_nesneler.intersection(imza_nesneler))
            if eslesen > en_iyi_eslesme:
                en_iyi_eslesme = eslesen
                en_iyi_oda = oda_adi

        return en_iyi_oda

    def odayi_ogren(self, oda_adi: str, imza_nesneler: list[str]) -> None:
        """Keşif modunda yeni bir odayı hafızaya ekler veya günceller."""
        temiz_oda = self._normalize_room_name(oda_adi)
        temiz_imzalar = self._normalize_signatures(imza_nesneler)

        if not temiz_oda or not temiz_imzalar:
            return

        mevcut_imzalar = self.known_rooms.get(temiz_oda, [])
        birlesik_imzalar = []
        for nesne in mevcut_imzalar + temiz_imzalar:
            if nesne not in birlesik_imzalar:
                birlesik_imzalar.append(nesne)

        self.known_rooms[temiz_oda] = birlesik_imzalar
        self._save_memory()

    def odayi_nesnelerden_ogren(self, oda_adi: str, yolo_nesneleri: list[dict]) -> None:
        """Ham YOLO çıktısından oda imzası çıkarıp kaydeder."""
        self.odayi_ogren(oda_adi, self.oda_imzasi_cikar(yolo_nesneleri))

    def describe(self) -> str:
        """Kısa durum özeti döndürür."""
        if not self.known_rooms:
            return "Henüz öğrenilmiş oda hafızası yok."

        oda_listesi = ", ".join(self.known_rooms.keys())
        return f"Öğrenilmiş odalar: {oda_listesi}"

    def _normalize_room_name(self, value: str) -> str:
        temiz = " ".join(value.split()).strip(" .,!?:;\"'")
        return temiz[:1].upper() + temiz[1:] if len(temiz) > 1 else temiz.upper()

    def _normalize_object_name(self, value: str) -> str:
        temiz = " ".join(value.split()).strip(" .,!?:;\"'")
        return temiz.lower()

    def _normalize_signatures(self, values: list[str]) -> list[str]:
        temiz_imzalar = []
        for value in values:
            if not isinstance(value, str):
                continue
            ad = self._normalize_object_name(value)
            if ad and ad not in temiz_imzalar:
                temiz_imzalar.append(ad)
        return temiz_imzalar
