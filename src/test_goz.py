import cv2
import socket
import numpy as np
from ultralytics import YOLO
from voice.tts import SesliYanit # Daha önce yazdığımız ses dosyan

# 1. Ayarlar
UDP_IP = "127.0.0.1"
UDP_PORT = 6050
model = YOLO("yolov8m.pt") # Küçük ve hızlı model
asistan = SesliYanit()

# 2. Soket Kurulumu
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print("[*] Bacanağın beyni devrede... Nesneleri tanımaya başlıyorum.")

last_detected = "" # Sürekli aynı şeyi söylememesi için

while True:
    data, addr = sock.recvfrom(65536)
    nparr = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is not None:
        # AI Analizi Yap (YOLOv8)
        results = model(frame, conf=0.7, verbose=False) # %70 güven altını görmezden gel
        
        # Görüntü üzerine kutucukları çiz
        annotated_frame = results[0].plot()
        
        # Tespit edilen nesneleri kontrol et
        for result in results:
            for box in result.boxes:
                label = model.names[int(box.cls[0])]
                
                # Eğer yeni bir nesne gördüyse ve son söylediği şey değilse konuş
                if label != last_detected:
                    print(f"[AI]: {label} tespit edildi!")
                    last_detected = label

        # Sonucu göster
        cv2.imshow("Yaver - AI Gözü", annotated_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cv2.destroyAllWindows()
sock.close()