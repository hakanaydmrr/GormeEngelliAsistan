import pyttsx3
import threading
import pythoncom
import time

class SesliYanit:
    def __init__(self):
        temp_engine = pyttsx3.init()
        self.voice_id = None
        voices = temp_engine.getProperty('voices')
        for v in voices:
            if "Turkish" in v.name or "tr" in v.id.lower():
                self.voice_id = v.id
                break
        if not self.voice_id:
            self.voice_id = voices[0].id
            
        print(f"[SİSTEM]: Ses motoru hazır. Kullanılan Ses: {self.voice_id}")
        del temp_engine
        self.konusuyor_mu = False

    def konus(self, metin, bekle=False): # 'bekle' parametresi ekledik
        if not metin: return
        
        if self.konusuyor_mu:
            print("[UYARI]: Asistan zaten konuşuyor, yeni istek reddedildi.")
            return

        def cal(konusulacak_metin):
            try:
                self.konusuyor_mu = True
                print(f"[SES ÇIKTI]: {konusulacak_metin}") # Sesin başladığını buradan teyit et
                pythoncom.CoInitialize()
                engine = pyttsx3.init()
                engine.setProperty('voice', self.voice_id)
                engine.setProperty('rate', 170)
                
                engine.say(konusulacak_metin)
                engine.runAndWait()
            except Exception as e:
                print(f"[SES HATASI]: {e}")
            finally:
                self.konusuyor_mu = False
                pythoncom.CoUninitialize()
                
        thread = threading.Thread(target=cal, args=(metin,))
        thread.start()

        if bekle:
            # Konuşma bitene kadar ana programı beklet (Mic ile çakışmasın)
            while self.konusuyor_mu:
                time.sleep(0.1)