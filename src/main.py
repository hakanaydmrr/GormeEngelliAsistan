import cv2
import os
import time
from vision.detector import GormeEngelliGozu
from vision.llm_analyzer import ZekiAnalizci

def get_api_key():
    """
    Ana dizindeki 'secret' dosyasından API anahtarını güvenli bir şekilde okur.
    GitHub'a pushlamadan önce bu dosyanın .gitignore içinde olduğundan emin olun.
    """
    secret_path = "secret"
    
    # Eğer terminalden src içinden çalıştırıyorsan bir üst dizine bakması gerekebilir
    if not os.path.exists(secret_path):
        secret_path = "../secret"

    try:
        with open(secret_path, "r") as f:
            key = f.read().strip()
            if not key:
                print("[HATA]: 'secret' dosyası boş!")
                return None
            return key
    except FileNotFoundError:
        print("[HATA]: 'secret' dosyası bulunamadı!")
        print("Lütfen ana dizinde 'secret' isimli bir dosya oluşturup API anahtarınızı içine yapıştırın.")
        return None

def main():
    # 1. API ANAHTARINI GİZLİ DOSYADAN ÇEK
    API_KEY = get_api_key()
    
    if not API_KEY:
        return # Anahtar yoksa sistemi başlatma

    try:
        # Sistem bileşenlerini başlatıyoruz
        goz = GormeEngelliGozu()
        beyin = ZekiAnalizci(API_KEY)
        kamera = cv2.VideoCapture(0)

        if not kamera.isOpened():
            print("Hata: Kamera erişimi sağlanamadı!")
            return

        print("\n--- SİSTEM AKTİF ---")
        print("Hızlı Tespit (YOLO) çalışıyor.")
        print("Detaylı analiz (Gemini) için 'a' tuşuna basın.")
        print("Çıkış yapmak için 'q' tuşuna basın.\n")

        while True:
            basarili, kare = kamera.read()
            if not basarili: break

            # 1. REFLEKS KATMANI: Hızlı Nesne Tespit (YOLO)
            nesneler = goz.nesneleri_tani(kare)
            
            for n in nesneler:
                x1, y1, x2, y2 = map(int, n["kutu"])
                etiket_metni = f"{n['ad'].upper()} %{int(n['guven']*100)}"
                
                # Görselleştirme (Kutu ve Yazı)
                cv2.rectangle(kare, (x1, y1), (x2, y2), (0, 255, 0), 3)
                cv2.rectangle(kare, (x1, y1 - 25), (x1 + 150, y1), (0, 255, 0), -1)
                cv2.putText(kare, etiket_metni, (x1, y1 - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

            cv2.imshow("Gorme Engelli Asistani", kare)

            tus = cv2.waitKey(1) & 0xFF
            
            # 2. BİLİŞSEL KATMAN: Derin Analiz (Gemini API)
            if tus == ord('a'):
                dosya_adi = "analiz_anlik.jpg"
                cv2.imwrite(dosya_adi, kare)
                
                print("[SİSTEM]: Bulut analizi başlatıldı, lütfen bekleyin...")
                cevap = beyin.analiz_et(dosya_adi)
                print(f"\n[ASİSTAN]: {cevap}\n")
                
                # Temizlik
                if os.path.exists(dosya_adi):
                    os.remove(dosya_adi)

            elif tus == ord('q'):
                print("Sistem kapatılıyor...")
                break

    except Exception as e:
        print(f"Beklenmedik bir hata oluştu: {e}")
    
    finally:
        if 'kamera' in locals():
            kamera.release()
        cv2.destroyAllWindows()
        print("Kamera ve pencereler kapatıldı.")

if __name__ == "__main__":
    main()