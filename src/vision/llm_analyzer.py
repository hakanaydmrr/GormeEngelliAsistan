import google.generativeai as genai
import PIL.Image
import os

class ZekiAnalizci:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        
        # Senin listende çalışan kesin modellerden biri:
        self.model_name = 'gemini-flash-lite-latest' 
        
        try:
            self.model = genai.GenerativeModel(self.model_name)
            print(f"[SİSTEM]: Bilişsel Katman Hazır. Model: {self.model_name}")
        except Exception as e:
            print(f"[HATA]: Model yüklenemedi: {e}")

    def analiz_et(self, resim_yolu, soru="Bu görüntüde ne görüyorsun? Görme engelli birine anlatır gibi kısa ve net açıkla."):
        try:
            if not os.path.exists(resim_yolu):
                return "Hata: Görüntü dosyası bulunamadı."

            img = PIL.Image.open(resim_yolu)
            
            # API Çağrısı
            response = self.model.generate_content([soru, img])
            
            if response and response.text:
                return response.text
            else:
                return "API yanıtı boş döndü, lütfen tekrar deneyin."
                
        except Exception as e:
            # 429 hatası alırsan burası çalışacak
            if "429" in str(e):
                return "Şu an çok yoğunum (Kota doldu), lütfen 30 saniye sonra tekrar dene."
            return f"Analiz hatası (Teknik): {str(e)}"