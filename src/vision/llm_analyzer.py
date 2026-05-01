import time
from google import genai
from PIL import Image

class ZekiAnalizci:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        
        # 404 HATASININ KESİN ÇÖZÜMÜ:
        # Genel isim yerine doğrudan versiyon numarası belirterek hedefi şaşırmasını engelliyoruz.
        self.model_id = 'gemini-1.5-flash-002' 
        
        self.system_instruction = (
            "Sen görme engelli bir birey için profesyonel bir 'Görsel Yardımcı'sın. "
            "Kullanıcının sorusuna göre görüntüyü analiz et. "
            "Daima TAM ve navigasyon odaklı cümleler kur. "
            "Cevapların en fazla 2 cümle olsun."
        )
        print(f"[SİSTEM]: Bilişsel Katman Stabil Modda. Aktif Model: {self.model_id}")

    def analiz_et(self, pil_image, soru="Önümde ne var?"):
        try:
            if pil_image is None: return "Görüntü verisi alınamadı."

            # Doğrudan API çağrısı
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[soru, pil_image],
                config={
                    "system_instruction": self.system_instruction,
                    "max_output_tokens": 120,
                    "temperature": 0.4
                }
            )

            if response and response.text:
                return response.text.strip()
            
            return "Şu an net bir görüntü alamadım."

        except Exception as e:
            error_msg = str(e)
            
            # KOTA HATASI (429) YÖNETİMİ
            if "429" in error_msg:
                print("\n[KOTA KORUMASI]: İstek sınırına ulaşıldı. 15 saniye sistem dinlendiriliyor...")
                time.sleep(15) # Sistemi zorla dinlendir ki Google API anahtarını banlamasın
                return "Şu an çok hızlı ilerliyoruz Furkan, sistemin dinlenmesi için biraz bekleyelim."
            
            # SÜRÜM HATASI (404) YÖNETİMİ
            elif "404" in error_msg:
                print(f"\n[UYARI]: {self.model_id} bulunamadı. Hızlı yedek modele geçiliyor...")
                # Eğer 002 sürümü de patlarsa, Google'ın en hızlı ve hafif modeli olan 8B'ye geçiş yap.
                self.model_id = 'gemini-1.5-flash-8b'
                return "Model güncelleniyor, lütfen sorunu tekrar eder misin?"
            
            print(f"[API HATASI]: {error_msg}")
            return "Teknik bir sorun oluştu."