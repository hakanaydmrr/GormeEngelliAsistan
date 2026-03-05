import cv2
from ultralytics import YOLO

class GormeEngelliGozu:
    def __init__(self):
        # 's' (small) modeli 1650 kartın için idealdir ve daha zekidir
        self.model = YOLO('yolov8m.pt') 

    def nesneleri_tani(self, kare):
        # conf=0.4 ekleyerek %40 altındaki tahminleri otomatik eliyoruz
        sonuclar = self.model(kare, stream=True, verbose=False, conf=0.4)
        bulunan_nesneler = []

        for r in sonuclar:
            for kutu in r.boxes:
                kords = kutu.xyxy[0].tolist()
                sinif_id = int(kutu.cls[0])
                ad = self.model.names[sinif_id]
                guven_skoru = float(kutu.conf[0])

                bulunan_nesneler.append({
                    "ad": ad,
                    "kutu": kords,
                    "guven": guven_skoru,
                    "merkez_x": (kords[0] + kords[2]) / 2
                })
        
        return bulunan_nesneler