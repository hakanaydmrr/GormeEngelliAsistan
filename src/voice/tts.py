import pyttsx3
import threading

class SesliYanit:
    def __init__(self):
        self.engine = pyttsx3.init()
        
        # 1. Türkçe sesi bul ve sabitle
        self.voice_id = None
        voices = self.engine.getProperty('voices')
        
        # Windows'taki Türkçe ses paketlerini ara
        for v in voices:
            if "Turkish" in v.name or "tr" in v.id.lower():
                self.voice_id = v.id
                break
        
        # Eğer bulunamazsa ilk varsayılan sesi al (genelde İngilizce olur)
        if not self.voice_id:
            self.voice_id = voices[0].id
            
        self.engine.setProperty('voice', self.voice_id)
        self.engine.setProperty('rate', 160)
        
        print("[SİSTEM]: Ses motoru Türkçe olarak sabitlendi.")

    def konus(self, metin):
        if not metin: return
        
        def cal():
            # Her seferinde yeni bir engine başlatmak, sesin kesilmesini önler
            engine = pyttsx3.init()
            engine.setProperty('voice', self.voice_id)
            engine.setProperty('rate', 160)
            engine.say(metin)
            engine.runAndWait()
            
        # Threading ile görüntünün donmasını engelle
        thread = threading.Thread(target=cal)
        thread.start()