from datetime import time

import cv2
import os
import socket
import numpy as np
import threading
import speech_recognition as sr
from PIL import Image
from vision.llm_analyzer import ZekiAnalizci 
from voice.tts import SesliYanit

# --- YAPILANDIRMA ---
WAKE_WORD = "asistan"
UDP_IP = "127.0.0.1"
UDP_PORT = 6050
son_kare = None 
kilid = threading.Lock()

def get_api_key():
    for path in ["secret", "../secret"]:
        if os.path.exists(path):
            with open(path, "r") as f: return f.read().strip()
    return None

def unity_goz_dongusu():
    global son_kare
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    while True:
        try:
            data, _ = sock.recvfrom(65536)
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                with kilid: son_kare = frame.copy()
                cv2.imshow("Yaver - Goz", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'): break
        except: continue

def profesyonel_ses_al(recognizer, source):
    """Gürültü filtresi artırılmış ses algılama."""
    try:
        recognizer.adjust_for_ambient_noise(source, duration=0.8)
        
        recognizer.energy_threshold = 1000 
        
        print("[SİSTEM]: Dinliyorum...")
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)
        return recognizer.recognize_google(audio, language="tr-TR")
    except:
        return None

def main():
    global son_kare
    api_key = get_api_key()
    if not api_key: return

    beyin = ZekiAnalizci(api_key)
    asistan_ses = SesliYanit()
    threading.Thread(target=unity_goz_dongusu, daemon=True).start()

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True

    print(f"[SİSTEM]: Yaver Hazır. '{WAKE_WORD}' diyerek başlayabilirsiniz.")

    with sr.Microphone() as source:
        while True:
            try:
                audio = recognizer.listen(source, timeout=2, phrase_time_limit=3)
                if WAKE_WORD in recognizer.recognize_google(audio, language="tr-TR").lower():
                    asistan_ses.konus("Efendim Furkan?", bekle=True)
                    

                    deneme = 0
                    while deneme < 3:
                        soru = profesyonel_ses_al(recognizer, source)
                        if soru:
                            print(f"[KULLANICI]: {soru}")
                            with kilid:
                                if son_kare is not None:
                                    # Görüntü Dönüşümü
                                    img = Image.fromarray(cv2.cvtColor(son_kare, cv2.COLOR_BGR2RGB))
                                    cevap = beyin.analiz_et(img, soru=soru)
                                    print(f"[ASİSTAN]: {cevap}")
                                    asistan_ses.konus(cevap, bekle=True)
                                    
                                    time.sleep(3) # Cevap sonrası kısa bir bekleme
                                
                                    if "tekrar sorar mısın" not in cevap.lower() and "hata" not in cevap.lower():
                                        break 
                                    else:
                                        deneme += 1 # Bir deneme hakkı düş ve tekrar 'Dinliyorum' aşamasına geç
                                else:
                                    asistan_ses.konus("Unity'den görüntü gelmiyor.", bekle=True)
                                    break
                        else:
                            deneme += 1
                            if deneme < 3:
                                asistan_ses.konus("Anlayamadım, tekrar eder misiniz?", bekle=True)
            except: continue

if __name__ == "__main__":
    main()