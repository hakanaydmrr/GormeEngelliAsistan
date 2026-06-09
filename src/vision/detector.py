import cv2
import time
from ultralytics import YOLO
from .latency_logger import log_latency

class GormeEngelliGozu:
    def __init__(self, model_path="yolov8m.pt"):
        # Model yükleme
        self.model = YOLO(model_path)
        # COCO veri kümesindeki Türkçe isim eşleştirmeleri
        self.classes = self.model.names

    def nesneleri_tani(self, frame):
        """
        Görüntüdeki nesneleri tanır, merkez koordinatlarını, kapladığı alan oranını
        ve merkezde olup olmadığını hesaplar.
        """
        start_time = time.time()
        results = self.model(frame, verbose=False)
        local_latency_ms = (time.time() - start_time) * 1000
        log_latency("local_reflex", local_latency_ms, {"frame_shape": frame.shape})
        tespitler = []

        # Ekran boyutlarını alıyoruz (Normalizasyon için)
        h, w, _ = frame.shape
        ekran_alani = w * h
        
        # Ekranın merkez şeridinin sınırları (Yürüyüş yolu: %30 ile %70 arası)
        merkez_sol = w * 0.3
        merkez_sag = w * 0.7

        for r in results:
            boxes = r.boxes
            for box in boxes:
                # Koordinatları alıyoruz: x1, y1 (sol üst) - x2, y2 (sağ alt)
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                ad = self.classes[cls]

                if conf > 0.45:  # Güven eşiği
                    merkez_x = (x1 + x2) / 2
                    merkez_y = (y1 + y2) / 2
                    
                    # --- REFLEX LAYER İÇİN YENİ MATEMATİKSEL HESAPLAMALAR ---
                    # Nesnenin piksel alanını bulup toplam ekrana oranlıyoruz (0.0 ile 1.0 arası)
                    nesne_genislik = x2 - x1
                    nesne_yukseklik = y2 - y1
                    nesne_alani = nesne_genislik * nesne_yukseklik
                    alan_orani = nesne_alani / ekran_alani
                    
                    # Nesne tam kullanıcının önünde mi (merkez şeritte mi?)
                    onunde_mi = merkez_sol <= merkez_x <= merkez_sag
                    # --------------------------------------------------------

                    tespitler.append({
                        "ad": ad,
                        "guven": conf,
                        "merkez_x": merkez_x,
                        "merkez_y": merkez_y,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "width": nesne_genislik,
                        "height": nesne_yukseklik,
                        "alan_orani": alan_orani,  # Ne kadar yakın olduğunu söyler
                        "onunde_mi": onunde_mi     # Tam çarpma rotasında mı olduğunu söyler
                    })

        return tespitler