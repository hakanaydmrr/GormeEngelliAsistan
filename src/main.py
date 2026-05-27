import cv2
import numpy as np
import socket
import threading
import speech_recognition as sr
from PIL import Image
import os
from dotenv import load_dotenv
from pathlib import Path

from conversation import AssistantProfileStore, IntentRouter, WeatherService
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


def normalize_tr(s: str) -> str:
    s = s.lower()
    s = s.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    return " ".join(s.split()).strip()


def wake_word_matches(text: str, wake_word: str = WAKE_WORD) -> bool:
    """Wake word'u otomatik tanıma varyasyonlarına karşı daha toleransli yakalar."""
    t = normalize_tr(text)
    w = normalize_tr(wake_word)

    # Çok basit varyantlar: asistan / asistanı / asislan / asilstan gibi hataları azalt
    # Örn: "asistan" kelimesinde aradaki harfler kaymışsa bile en azından "istan" yakalayabilir.
    if w in t:
        return True

    # "istan" sonunu yakala (en az 5 karakter: istan)
    if "istan" in t:
        # ama rastgele "sistan" vb. olmasın diye minimal bağlam
        return "as" in t or t.startswith("a")

    return False



def get_api_key():
    """API anahtarını .env dosyasından güvenli şekilde alır."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[HATA]: GEMINI_API_KEY bulunamadı! .env dosyasını kontrol edin.")
    return api_key


def unity_udp_dinleyici():
    global son_kare
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"[SİSTEM]: Unity UDP dinleyicisi başlatıldı: {UDP_IP}:{UDP_PORT}")

    while True:
        try:
            data, _ = sock.recvfrom(65536)
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is not None:
                with kilid:
                    son_kare = frame.copy()
                cv2.imshow("Yaver - Göz (UDP)", frame)
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


def soruyu_zenginlestir(soru, sahne_ozeti, profil_ozeti):
    temiz_soru = " ".join(soru.lower().split())

    return (
        "Sen görme engelli bir kullanıcıya yardımcı olan bir görsel asistansın.\n"
        f"Kullanıcının sorusu: {soru}\n"
        f"Normalleştirilmiş soru: {temiz_soru}\n"
        f"Kullanıcı profili: {profil_ozeti}\n"
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


def run_visual_reply(beyin, gozu, asistan_ses, soru, kare_kopyasi, profil_store):
    img = Image.fromarray(cv2.cvtColor(kare_kopyasi, cv2.COLOR_BGR2RGB))
    nesneler = gozu.nesneleri_tani(kare_kopyasi)
    sahne_ozeti = sahne_ozeti_olustur(nesneler, kare_kopyasi.shape[1])
    sorgu = soruyu_zenginlestir(soru, sahne_ozeti, profil_store.describe())

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
    global son_kare

    api_key = get_api_key()
    if not api_key:
        return

    beyin = ZekiAnalizci(api_key)
    gozu = GormeEngelliGozu()
    asistan_ses = SesliYanit()
    profil_store = AssistantProfileStore()
    router = IntentRouter()
    weather_service = WeatherService()
    konusma_gecmisi = []

    threading.Thread(target=unity_udp_dinleyici, daemon=True).start()

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.energy_threshold = 600
    recognizer.dynamic_energy_adjustment_damping = 0.15

    print("[SİSTEM]: Yaver Hazır. 'Asistan' diyerek başlayabilirsiniz.")
    print(f"[SİSTEM]: Aktif kullanıcı: {profil_store.get_preferred_name()}")

    with sr.Microphone(device_index=1) as source:
        print("[SİSTEM]: SteelSeries Arctis 5 Chat bağlandı. Gürültü dengeleniyor...")
        recognizer.adjust_for_ambient_noise(source, duration=1.5)
        print("[SİSTEM]: Mikrofon hazır. 'Asistan' diyerek başlayabilirsiniz.")
        print("[SİSTEM]: Dinliyorum...")

        while True:
            try:
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=2)

                try:
                    komut = recognizer.recognize_google(audio, language="tr-TR").lower()
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    print("[HATA]: Google konuşma servisine erişilemedi. İnternet/DNS bağlantısını kontrol edin.")
                    continue

                # Wake word yakalama (toleranslı)
                if wake_word_matches(komut):
                    # Ses eşiğini kısa süreliğine yeniden ayarla (dinleme kaymasını azaltır)
                    try:
                        recognizer.adjust_for_ambient_noise(source, duration=0.8)
                    except Exception:
                        pass

                    kullanici_adi = profil_store.get_preferred_name()
                    asistan_ses.konus(f"{kullanici_adi}, dinliyorum.", bekle=True)

                    print("[SİSTEM]: Sorunuzu bekliyorum...")
                    soru_audio = recognizer.listen(source, timeout=6, phrase_time_limit=8)


                    try:
                        soru = recognizer.recognize_google(soru_audio, language="tr-TR").strip()
                        print(f"[KULLANICI]: {soru}")
                        if not soru:
                            asistan_ses.konus("Soruyu tam anlayamadım, lütfen tekrar eder misiniz?", bekle=True)
                            continue
                    except sr.UnknownValueError:
                        # Tek retry: bazen tek seferlik dinleme bozuluyor
                        asistan_ses.konus("Biraz daha duymak ister misin? Tekrar eder misin?", bekle=True)
                        soru_audio_retry = recognizer.listen(source, timeout=4, phrase_time_limit=8)
                        try:
                            soru = recognizer.recognize_google(soru_audio_retry, language="tr-TR").strip()
                            print(f"[KULLANICI]: {soru}")
                            if not soru:
                                asistan_ses.konus("Tam anlayamadım. Lütfen tekrar eder misin?", bekle=True)
                                continue
                        except sr.UnknownValueError:
                            asistan_ses.konus("Sorunuzu anlayamadım.", bekle=True)
                            continue

                    except sr.RequestError:
                        asistan_ses.konus("İnternet bağlantısında sorun var.", bekle=True)
                        continue

                    route = router.route(soru)

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
                        kare_kopyasi = None
                        with kilid:
                            if son_kare is not None:
                                kare_kopyasi = son_kare.copy()

                        if kare_kopyasi is not None:
                            yanit = run_visual_reply(beyin, gozu, asistan_ses, soru, kare_kopyasi, profil_store)
                            konusma_gecmisi.append(f"Kullanıcı: {soru}")
                            konusma_gecmisi.append(f"Asistan: {yanit}")
                        else:
                            yanit = "Kamera görüntüsü alınamadı."
                            konusma_gecmisi.append(f"Kullanıcı: {soru}")
                            konusma_gecmisi.append(f"Asistan: {yanit}")
                            asistan_ses.konus(yanit, bekle=True)
                        continue

                    if route.intent in {"greeting", "small_talk", "unknown"}:
                        yanit = run_text_reply(beyin, asistan_ses, soru, profil_store, konusma_gecmisi)
                        konusma_gecmisi.append(f"Kullanıcı: {soru}")
                        konusma_gecmisi.append(f"Asistan: {yanit}")
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
