import PIL.Image
import os
import google.generativeai as genai

class ZekiAnalizci:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        
        # 1. Model ismini daha güncel bir modele çevirdik
        self.model_name = 'gemini-2.5-flash' 
        
        # 2. Güvenlik filtrelerini kapattık (Bazen insan yüzü var diye analizi reddediyor)
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        try:
            self.model = genai.GenerativeModel(self.model_name, safety_settings=self.safety_settings)
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

            # Daha güvenli yanıt kontrolü
            if response and hasattr(response, 'text') and response.text and response.text.strip():
                return response.text.strip()
            else:
                return "API yanıtı boş döndü. (İçerik filtreye takılmış olabilir)"
                
        except Exception as e:
            if "429" in str(e):
                return "Kota doldu, lütfen biraz bekleyin."
            return f"Analiz hatası: {str(e)}"
