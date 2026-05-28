import cv2
import numpy as np
import socket
import threading
import time
import speech_recognition as sr
from PIL import Image
import os
from dotenv import load_dotenv
from pathlib import Path

from conversation import AssistantProfileStore, IntentRouter, SpatialMemoryStore, WeatherService
from voice.tts import SesliYanit
from vision.llm_analyzer import ZekiAnalizci
from vision.detector import GormeEngelliGozu

dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("[HATA]: GEMINI_API_KEY bulunamadı! .env dosyasını kontrol edin.")
else:
    print("[SİSTEM]: API anahtarı başarıyla yüklendi.")

UDP_IP = "127.0.0.1"
UDP_PORT = 6050

son_kare = None
kilid = threading.Lock()
WAKE_WORD = "asistan"

# --- 1. ADIM: DİNAMİK KONUM BİLGİSİ İÇİN GLOBAL DEĞİŞKEN ---
mevcut_konum = "Bilinmeyen Oda"


def normalize_tr(s: str) -> str:
    s = s.lower()
    s = s.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    return " ".join(s.split()).strip()


def wake_word_matches(text: str, wake_word: str = WAKE_WORD) -> bool:
    """Wake word'u otomatik tanıma varyasyonlarına karşı daha toleransli yakalar."""
    t = normalize_tr(text)
    w = normalize_tr(wake_word)

    if w in t:
        return True

    if "istan" in t:
        return "as" in t or t.startswith("a")

    return False


def is_wake_word_only(text: str) -> bool:
    temiz = normalize_tr(text)
    return temiz in {WAKE_WORD, "hey " + WAKE_WORD, WAKE_WORD + "!"} or temiz.startswith(WAKE_WORD) and len(temiz.split()) <= 2


def get_api_key():
    """API anahtarını .env dosyasından güvenli şekilde alır."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[HATA]: GEMINI_API_KEY bulunamadı! .env dosyasını kontrol edin.")
    return api_key


def unity_udp_dinleyici(gozu, spatial_store):
    global son_kare, mevcut_konum  # Konum bilgisini güncellemek için global ekledik
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"[SİSTEM]: Unity UDP dinleyicisi başlatıldı: {UDP_IP}:{UDP_PORT}")

    while True:
        try:
            data, _ = sock.recvfrom(65536)
            
            # --- 1. ADIM: BİRLEŞİK UDP PAKETİNİ PARÇALAMA ---
            ayrac_index = data.find(b"|")
            if ayrac_index != -1:
                # Ayracın sol tarafı konum metnidir (Örn: Unity'den gönderilen "Mutfak")
                mevcut_konum = data[:ayrac_index].decode('utf-8')
                # Ayracın sağ tarafı ise saf resim byte verisidir
                resim_verisi = data[ayrac_index + 1:]
            else:
                resim_verisi = data
            # ------------------------------------------------

            nparr = np.frombuffer(resim_verisi, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is not None:
                with kilid:
                    son_kare = frame.copy()
                # OpenCV pencere başlığında anlık oda bilgisini de gösteriyoruz
                cv2.imshow(f"Yaver - Goz ({mevcut_konum})", frame)
                cv2.waitKey(1)
        except Exception:
            continue


def sahne_ozeti_olustur(nesneler, kare_genisligi):
    if not nesneler:
        return "Belirgin nesne tespit edilemedi."

    parcalar = []
    sinir_sol = kare_genisligi / 3
    sinir_sag = (kare_genisligi * 2) / 3

    for nesne in nesneler[:6]:
        konum_x = nesne.get("merkez_x", 0)
        if konum_x < sinir_sol:
            konum = "solda"
        elif konum_x < sinir_sag:
            konum = "ortada"
        else:
            konum = "sağda"

        ad = nesne.get("ad", "bilinmeyen nesne")
        guven = nesne.get("guven", 0.0)
        parcalar.append(f"{ad} {konum} (%{int(guven * 100)} güven)")

    return ", ".join(parcalar)


def soruyu_zenginlestir(soru, sahne_ozeti, profil_ozeti, anlik_konum):
    temiz_soru = " ".join(soru.lower().split())

    return (
        "Sen görme engelli bir kullanıcıya yardımcı olan bir görsel asistansın.\n"
        f"Kullanıcının sorusu: {soru}\n"
        f"Normalleştirilmiş soru: {temiz_soru}\n"
        f"Kullanıcı profili: {profil_ozeti}\n"
        f"Kullanıcının şu anki konumu: {anlik_konum}\n"  # Gemini'a kullanıcının odasını fısıldıyoruz
        f"Görüntü ipuçları: {sahne_ozeti}\n"
        "Sadece görsele dayalı, net, doğal ve tam bir Türkçe cevap ver.\n"
        "Kullanıcı ne soruyorsa ona odaklan; nesne, kişi, konum, renk, metin, engel, ortam veya güvenli geçiş bilgisini gerekiyorsa kullan.\n"
        "Emin değilsen bunu açıkça söyle ama cevabı yarım bırakma."
    )


def genel_fallback_cevap(soru, sahne_ozeti):
    temiz_soru = " ".join(soru.lower().split())

    if sahne_ozeti and sahne_ozeti != "Belirgin nesne tespit edilemedi.":
        return f"Görüntüde seçebildiğim kadarıyla {sahne_ozeti} var."

    if any(
        anahtar in temiz_soru
        for anahtar in ["ne", "kim", "nerede", "hangi", "var mı", "görüyor", "yazıyor", "okuyor", "nasıl"]
    ):
        return "Görüntüden net ayırt edebildiğim belirgin bir detay yok; daha net bir açıyla tekrar bakabilirim."

    return "Görüntüden net bir çıkarım yapamadım; istersen sorunu biraz daha ayrıntılandır."


def sohbet_baglamini_olustur(profil_store, gecmis):
    baglam = (
        f"Kullanıcı profili: {profil_store.describe()}.\n"
        "Ton: sıcak, zeki, esprili ama saygılı.\n"
        "Kullanıcı ile günlük hayatta konuşur gibi doğal ve kısa cevaplar ver."
    )

    if gecmis:
        son_mesajlar = "\n".join(gecmis[-4:])
        baglam = f"{baglam}\nSon sohbet akışı:\n{son_mesajlar}"

    return baglam


def run_visual_reply(beyin, gozu, asistan_ses, soru, kare_kopyasi, profil_store, anlik_konum, spatial_store):
    img = Image.fromarray(cv2.cvtColor(kare_kopyasi, cv2.COLOR_BGR2RGB))
    nesneler = gozu.nesneleri_tani(kare_kopyasi)
    sahne_ozeti = sahne_ozeti_olustur(nesneler, kare_kopyasi.shape[1])
    tahmin_edilen_oda = spatial_store.oda_tahmin_et(nesneler)
    etkin_konum = tahmin_edilen_oda or anlik_konum
    
    # soruyu_zenginlestir fonksiyonuna etkin_konum parametresini ekledik
    sorgu = soruyu_zenginlestir(soru, sahne_ozeti, profil_store.describe(), etkin_konum)

    cevap = beyin.analiz_et(img, soru=sorgu)
    duzgun_cevap = " ".join((cevap or "").split())

    if len(duzgun_cevap) < 20 or len(duzgun_cevap.split()) < 4:
        duzgun_cevap = genel_fallback_cevap(soru, sahne_ozeti)

    print(f"[ASİSTAN - GÖRSEL]: {duzgun_cevap}")
    asistan_ses.konus(duzgun_cevap, bekle=True)
    return duzgun_cevap


def run_text_reply(beyin, asistan_ses, soru, profil_store, gecmis):
    baglam = sohbet_baglamini_olustur(profil_store, gecmis)
    cevap = beyin.sohbet_et(soru, baglam=baglam)
    duzgun_cevap = " ".join((cevap or "").split())

    print(f"[ASİSTAN - SOHBET]: {duzgun_cevap}")
    asistan_ses.konus(duzgun_cevap, bekle=True)
    return duzgun_cevap


def main():
    global son_kare, mevcut_konum

    api_key = get_api_key()
    if not api_key:
        return

    beyin = ZekiAnalizci(api_key)
    gozu = GormeEngelliGozu()
    asistan_ses = SesliYanit()
    profil_store = AssistantProfileStore()
    router = IntentRouter()
    spatial_store = SpatialMemoryStore()
    weather_service = WeatherService()
    konusma_gecmisi = []

    threading.Thread(target=unity_udp_dinleyici, args=(gozu, spatial_store), daemon=True).start()

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.energy_threshold = 600
    recognizer.dynamic_energy_adjustment_damping = 0.15

    print("[SİSTEM]: Yaver Hazır. 'Asistan' diyerek başlayabilirsiniz.")
    print(f"[SİSTEM]: Aktif kullanıcı: {profil_store.get_preferred_name()}")

    device_index = 1
    try:
        mic_names = sr.Microphone.list_microphone_names()
        if not mic_names or device_index >= len(mic_names):
            print(f"[WARN]: device_index={device_index} bulunamadı. Default mikrofon kullanılacak.")
            device_index = None
        else:
            print(f"[SİSTEM]: Mikrofon seçildi: index={device_index} -> {mic_names[device_index]}")
    except Exception:
        print("[WARN]: Mikrofon listesi alınamadı. Default mikrofon deneniyor.")
        device_index = None

    with sr.Microphone(device_index=None) as source:
        # TTS sırasında mikrofon dinlemeyi durdurmayı garantiye almak için event kontrolü
        # (recognizer.listen çağrıları TTS bitmeden başlatılmayacak)
        # Mikrofon context'i tek sefer kurulsun; sonsuz döngü içinde yeniden açılmasın.
        try:
            recognizer.adjust_for_ambient_noise(source, duration=1.5)
        except Exception:
            pass

        print("[SİSTEM]: Mikrofon hazır. Dinliyorum...")

        while True:
            try:
                # Artık sadece wake word beklemiyoruz; gelen her konuşmayı değerlendiriyoruz.
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=6)
                try:
                    komut = recognizer.recognize_google(audio, language="tr-TR").strip()
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    print("[HATA]: Google konuşma servisine erişilemedi.")
                    continue

                if not komut:
                    continue

                print(f"[KULLANICI - HAM]: {komut}")
                route = router.route(komut)
                wake_word_var = wake_word_matches(komut)

                if wake_word_var and is_wake_word_only(komut):
                    try:
                        recognizer.adjust_for_ambient_noise(source, duration=0.8)
                    except Exception:
                        pass

                    kullanici_adi = profil_store.get_preferred_name()
                    asistan_ses.konus(f"{kullanici_adi}, dinliyorum.", bekle=True)

                    try:
                        while asistan_ses.is_speaking.is_set():
                            time.sleep(0.01)
                    except Exception:
                        pass

                    try:
                        recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    except Exception:
                        pass

                    print("[SİSTEM]: Sorunuzu bekliyorum...")
                    soru_audio = recognizer.listen(source, timeout=6, phrase_time_limit=8)

                    try:
                        soru = recognizer.recognize_google(soru_audio, language="tr-TR").strip()
                    except sr.UnknownValueError:
                        asistan_ses.konus("Biraz daha duymak ister misin? Tekrar eder misin?", bekle=True)
                        soru_audio_retry = recognizer.listen(source, timeout=4, phrase_time_limit=8)
                        try:
                            soru = recognizer.recognize_google(soru_audio_retry, language="tr-TR").strip()
                        except sr.UnknownValueError:
                            asistan_ses.konus("Sorunuzu anlayamadım.", bekle=True)
                            continue
                    except sr.RequestError:
                        asistan_ses.konus("İnternet bağlantısında sorun var.", bekle=True)
                        continue
                else:
                    soru = komut

                if not soru:
                    asistan_ses.konus("Soruyu tam anlayamadım, lütfen tekrar eder misiniz?", bekle=True)
                    continue

                print(f"[KULLANICI]: {soru}")

                if route.intent == "name_change":
                    guncel_profil = profil_store.update_from_text(soru)
                    yeni_isim = guncel_profil["preferred_name"]
                    yanit = f"Tamam {yeni_isim}, bundan sonra sana böyle sesleneceğim."
                    konusma_gecmisi.append(f"Kullanıcı: {soru}")
                    konusma_gecmisi.append(f"Asistan: {yanit}")
                    asistan_ses.konus(yanit, bekle=True)
                    continue

                if route.intent == "weather":
                    guncel_profil = profil_store.update_from_text(soru)
                    sehir = guncel_profil["city"]
                    hava_bilgisi = weather_service.get_weather_text(sehir)
                    konusma_gecmisi.append(f"Kullanıcı: {soru}")
                    konusma_gecmisi.append(f"Asistan: {hava_bilgisi}")
                    print(f"[ASİSTAN - HAVA]: {hava_bilgisi}")
                    asistan_ses.konus(hava_bilgisi, bekle=True)
                    continue

                if route.intent == "vision":
                    with kilid:
                        kare_kopyasi = son_kare.copy() if son_kare is not None else None

                    if kare_kopyasi is not None:
                        yanit = run_visual_reply(beyin, gozu, asistan_ses, soru, kare_kopyasi, profil_store, mevcut_konum, spatial_store)
                        konusma_gecmisi.append(f"Kullanıcı: {soru}")
                        konusma_gecmisi.append(f"Asistan: {yanit}")
                    else:
                        yanit = "Kamera görüntüsü alınamadı."
                        konusma_gecmisi.append(f"Kullanıcı: {soru}")
                        konusma_gecmisi.append(f"Asistan: {yanit}")
                        asistan_ses.konus(yanit, bekle=True)
                    continue

                yanit = run_text_reply(beyin, asistan_ses, soru, profil_store, konusma_gecmisi)
                konusma_gecmisi.append(f"Kullanıcı: {soru}")
                konusma_gecmisi.append(f"Asistan: {yanit}")

            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                print(f"[DEBUG - SESSİZ DÖNGÜ]: {e}")
                continue



if __name__ == "__main__":
    main()
