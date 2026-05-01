import mss
import numpy as np
import cv2

def ekran_izle():
    sct = mss.mss()
    
    # İzlenecek ekran bölgesi (Unity penceresine göre ayarlayacağız)
    # Şimdilik ekranın sol üst köşesinden 800x600 bir alan alalım
    monitor = {"top": 100, "left": 50, "width": 700, "height": 500}

    print("[SİSTEM]: Ekran yakalama başladı. Çıkış için 'q' basın.")

    while True:
        # Ekran görüntüsünü yakala
        ekran_goruntusu = sct.grab(monitor)
        
        # Görüntüyü OpenCV formatına (numpy array) çevir
        kare = np.array(ekran_goruntusu)
        
        # mss BGRA formatında verir, biz bunu BGR yapmalıyız
        kare = cv2.cvtColor(kare, cv2.COLOR_BGRA2BGR)

        # Ekranda göster
        cv2.imshow("Asistanin Gozu (Sanal)", kare)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    ekran_izle()