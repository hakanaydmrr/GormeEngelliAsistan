import cv2
import os
from vision.detector import GormeEngelliGozu
from vision.llm_analyzer import ZekiAnalizci 
from voice.tts import SesliYanit

def get_api_key():
    secret_path = "secret"
    if not os.path.exists(secret_path):
        secret_path = "../secret"
    try:
        with open(secret_path, "r") as f:
            return f.read().strip()
    except Exception:
        print("[HATA]: 'secret' dosyası bulunamadı!")
        return None

def main():
    API_KEY = get_api_key()
    if not API_KEY: return

    # Bileşenleri başlat
    goz = GormeEngelliGozu()
    beyin = ZekiAnalizci(API_KEY)
    sesli_asistan = SesliYanit() 
    
    kamera = cv2.VideoCapture(0)
    if not kamera.isOpened():
        print("Hata: Kamera erişimi sağlanamadı!")
        return

    print("\n--- SİSTEM AKTİF ---")
    print("Detaylı analiz için 'a', çıkış için 'q' tuşuna basın.")

    try:
        while True:
            basarili, kare = kamera.read()
            if not basarili: break

            # 1. YOLU (Hızlı Tespit - Ekrana anlık kutu çizer)
            nesneler = goz.nesneleri_tani(kare)
            for n in nesneler:
                x1, y1, x2, y2 = map(int, n["kutu"])
                cv2.rectangle(kare, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # 2. Görüntüyü Göster
            cv2.imshow("Görme Engelli Asistan", kare)

            # 3. Tuş Kontrolü (Donmayı önlemek için döngünün en sonunda)
            tus = cv2.waitKey(1) & 0xFF
            
            if tus == ord('a'):
                print("[SİSTEM]: Bulut analizi başlatıldı...")
                dosya_adi = "analiz_anlik.jpg"
                cv2.imwrite(dosya_adi, kare)

                # Gemini Analizi
                cevap = beyin.analiz_et(dosya_adi)

                # Seslendirme Süzgeci
                if (
                    cevap
                    and len(cevap.strip()) > 5
                    and "Analiz hatası" not in cevap
                    and "Hata:" not in cevap
                    and "Kota doldu" not in cevap
                    and "API yanıtı boş" not in cevap
                ):
                    print(f"\n[ASİSTAN]: {cevap}\n")
                    sesli_asistan.konus(cevap)
                    cv2.waitKey(3000)  # Sonuçları görmek için kısa bir bekleme
                else:
                    print(f"\n[SİSTEM]: {cevap}\n")

                if os.path.exists(dosya_adi):
                    try:
                        os.remove(dosya_adi)
                    except:
                        pass

            elif tus == ord('t'):
                print("[SİSTEM]: Dil ayarı bildirimi tetiklendi.")
                sesli_asistan.konus("Seslendirme dili Türkçe olarak ayarlandı.", dil_bilgisi_ekle=True)

            elif tus == ord('q'):
                print("Sistem kapatılıyor...")
                break

    finally:
        # Kamera ve pencereleri kapat
        if 'kamera' in locals():
            kamera.release()
        cv2.destroyAllWindows()
        
        # --- SES DOSYALARINI TEMİZLE ---
        print("[SİSTEM]: Geçici ses dosyaları temizleniyor...")
        for dosya in os.listdir("."):
            if dosya.startswith("yanit_") and dosya.endswith(".mp3"):
                try:
                    os.remove(dosya)
                except Exception as e:
                    print(f"[UYARI]: {dosya} silinemedi: {e}")
        
        print("Kamera ve pencereler kapatıldı, temizlik tamamlandı.")

if __name__ == "__main__":
    main()
