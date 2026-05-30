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

PROJE_KOK = Path(__file__).resolve().parent.parent
dotenv_path = PROJE_KOK / ".env"
load_dotenv(dotenv_path=dotenv_path)

api_key = os.getenv("GEMINI_API_KEY1") or os.getenv("GEMINI_API_KEY")
if not api_key:
    print("[HATA]: .env dosyasında geçerli bir API anahtarı bulunamadı!")
else:
    print("[SİSTEM]: API anahtarları başarıyla yüklendi.")    

UDP_IP = "127.0.0.1"
UDP_PORT = 6050

son_kare = None
kilid = threading.Lock()
WAKE_WORD = "asistan"

# --- DİNAMİK KONUM BİLGİSİ İÇİN GLOBAL DEĞİŞKEN ---
mevcut_konum = "Bilinmeyen Oda"
anlik_radar=""


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
    """API anahtarını çoklu mimariye uygun şekilde doğrular."""
    api_key = os.getenv("GEMINI_API_KEY1") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[HATA]: API anahtarı doğrulanamadı!")
    return api_key


def unity_udp_dinleyici(gozu_nesnesi, spatial_store, asistan_ses):
    global son_kare, mevcut_konum, anlik_radar, anlik_pusula
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"[SİSTEM]: Unity UDP dinleyicisi başlatıldı: {UDP_IP}:{UDP_PORT}")

    KRITIK_ENGELLER = {"chair", "table", "desk", "box", "bed", "toilet", "door"}
    son_okunan_spiker = "" 

    while True:
        try:
            data, _ = sock.recvfrom(655360) 
            jpeg_baslangic = data.find(b'\xff\xd8')
            
            if jpeg_baslangic != -1:
                metin_kismi = data[:jpeg_baslangic].decode('utf-8', errors='ignore').strip()
                resim_bytes = data[jpeg_baslangic:]
                
                if len(metin_kismi) > 0:
                    parcalar = metin_kismi.split('|')
                    gelen_spiker = parcalar[1] if len(parcalar) > 1 else ""
                    anlik_radar = parcalar[2] if len(parcalar) > 2 else ""
                    
                    # Pusulayı güncelle
                    anlik_pusula = gelen_spiker.strip()
                    
                    # 🔥 DİNAMİK YÖNLENDİRME (Pusula verisi değişirse asistanı tetikle)
                    if "Rota yok" not in anlik_pusula and "Seni yönlendiriyorum" not in anlik_pusula:
                        if anlik_pusula != son_okunan_spiker:
                            print(f"[REHBER]: {anlik_pusula}")
                            asistan_ses.konus(anlik_pusula, bekle=False)
                            son_okunan_spiker = anlik_pusula
                
                # Resim işleme ve YOLO (Aynı kalacak)
                nparr = np.frombuffer(resim_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if frame is not None:
                    with kilid:
                        son_kare = frame.copy()
        except Exception as e:
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


def soruyu_zenginlestir(soru, sahne_ozeti, profil_ozeti, anlik_konum, pusula_verisi):
    return (
        "Sen bir NAVİGASYON ASİSTANISIN. Kullanıcıyı yatağa/hedefe en kısa yoldan ulaştırmakla görevlisin.\n"
        "NESNELERİ BETİMLEME. Sadece engelleri uyar.\n\n"
        
        f"KULLANICI VERİLERİ:\n"
        f"- Konum: {anlik_konum}\n"
        f"- Hedef Yönü (PUSULA): {pusula_verisi}\n"
        f"- Yol Üzerindeki Engeller: {sahne_ozeti}\n\n"
        
        "REHBERLİK PROTOKOLÜ (HAYATİ):\n"
        "1. KESİN EMİR: Kullanıcıya ilk cümlende mutlaka PUSULA VERİSİ'ni söyle. Örn: 'Hedef sağ arka tarafında, sağa dön.'\n"
        "2. ENGEL YÖNETİMİ: PUSULA VERİSİ ile yol üzerindeki nesneleri birleştir. 'Sağa dönmelisin ama önünde koltuk var, koltuğun solundan geçerek sağa yönel' de.\n"
        "3. KISITLAMA: Asla 15 kelimeyi geçme. Uzun anlatım yasak. Doğal, komut odaklı, insan sesli bir rehber ol.\n"
        "4. ODALANMA: Sadece 'nereye döneceğini' ve 'nasıl yürüyeceğini' söyle. Çevre betimlemesini sadece yürümeni engelleyen nesneler için yap.\n"
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

def run_text_reply(beyin, asistan_ses, soru, profil_store, gecmis):
    baglam = sohbet_baglamini_olustur(profil_store, gecmis)
    cevap = beyin.sohbet_et(soru, baglam=baglam)
    duzgun_cevap = " ".join((cevap or "").split())

    print(f"[ASİSTAN - SOHBET]: {duzgun_cevap}")
    asistan_ses.konus(duzgun_cevap, bekle=True) 
    return duzgun_cevap

def run_visual_reply(beyin, gozu, asistan_ses, soru, kare_kopyasi, profil_store, anlik_konum, radar_verisi, spatial_store, pusula_verisi):
    if kare_kopyasi is None:
        return "Görüntü verisi alınamadı."

    # --- 1. ADIM: ÇÖZÜNÜRLÜK VE İYİLEŞTİRME ---
    kare_kopyasi = cv2.resize(kare_kopyasi, (800, 600), interpolation=cv2.INTER_AREA)
    aydinlatilmis_kare = cv2.convertScaleAbs(kare_kopyasi, alpha=1.2, beta=40)
    keskinlestirme_matrisi = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    iyilestirilmis_kare = cv2.filter2D(aydinlatilmis_kare, -1, keskinlestirme_matrisi)

    img = Image.fromarray(cv2.cvtColor(iyilestirilmis_kare, cv2.COLOR_BGR2RGB))
    
    nesneler = gozu.nesneleri_tani(iyilestirilmis_kare)
    sahne_ozeti = sahne_ozeti_olustur(nesneler, iyilestirilmis_kare.shape[1])
    tahmin_edilen_oda = spatial_store.oda_tahmin_et(nesneler)
    etkin_konum = tahmin_edilen_oda or anlik_konum
    
    # --- 2. ADIM: ZENGİNLEŞTİRİLMİŞ SORGULAMA (Pusula Verisi ile) ---
    sorgu = soruyu_zenginlestir(soru, sahne_ozeti, profil_store.describe(), etkin_konum, pusula_verisi)
    
    if radar_verisi and "belirgin bir nesne yok" not in radar_verisi.lower():
        sorgu += f"\n\n[DİNAMİK RADAR VERİSİ]:\n{radar_verisi}"
    
    # --- 3. ADIM: ANALİZ ---
    cevap = beyin.analiz_et(img, soru=sorgu)
    duzgun_cevap = " ".join((cevap or "").split())

    if len(duzgun_cevap) < 20 or len(duzgun_cevap.split()) < 4:
        duzgun_cevap = genel_fallback_cevap(soru, sahne_ozeti)

    print(f"[ASİSTAN - GÖRSEL]: {duzgun_cevap}")
    asistan_ses.konus(duzgun_cevap, bekle=True)
    return duzgun_cevap

def main():
    global son_kare, mevcut_konum,anlik_radar
    anlik_pusula = "Yol tarifi bekleniyor..."

    # --- DOSYA KONTROLÜ VE SAF JSON OLARAK SEEDING ---
    try:
        import json
        json_path = Path(__file__).resolve().parent / "conversation" / "spatial_memory.json"
        
        if not json_path.exists() or json_path.stat().st_size == 0:
            print("[SİSTEM]: spatial_memory.json bulunamadı. İlk kurulum için odalar öğretiliyor...")
            
            varsayilan_hafiza = {
                "odalar": {
                    "Mutfak": {"nesneler": ["buzdolabı", "fırın", "mikrodalga", "ekmek kızartma makinesi", "lavabo", "bardak", "çatal", "bıçak"]},
                    "Oturma Odası": {"nesneler": ["televizyon", "koltuk", "sehpa", "kitaplık", "kumanda", "vazo"]},
                    "Yatak Odası": {"nesneler": ["yatak", "gardırop", "komodin", "yastık", "ayna", "lamba"]},
                    "Banyo": {"nesneler": ["çamaşır makinesi", "duş", "ayna", "havlu", "diş fırçası", "klozet"]}
                }
            }
            
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(varsayilan_hafiza, f, ensure_ascii=False, indent=4)
            
            print("[SİSTEM]: İlk odalar başarıyla oluşturuldu ve 'spatial_memory.json' dosyasına kaydedildi!")
    except Exception as e:
        print(f"[WARN]: İlk odalar otomatik yüklenirken bir hata oluştu: {e}")
    # -----------------------------------------------------------------------

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

    otopilot_hedefler = {
        "yatak": "Yatak", "yatak odası": "Yatak", "uyuyacağım": "Yatak", "uzanacağım": "Yatak",
        "koltuk": "Koltuk", "oturma odası": "Koltuk", "dinleneceğim": "Koltuk",
        "masa": "YemekMasasi", "yemek": "YemekMasasi", "sofra": "YemekMasasi",
        "lavabo": "Lavabo", "elimi yıkayacağım": "Lavabo", "tuvalet": "Lavabo"
    }

    threading.Thread(target=unity_udp_dinleyici, args=(gozu, spatial_store, asistan_ses), daemon=True).start()

    # -----------------------------------------------------------
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False  # Dinamik eşiği kapattık
    recognizer.energy_threshold = 300           # Arctis 5 için sabit ve kararlı gürültü barajı
    recognizer.pause_threshold = 0.8            # Cümlen bittiğinde kilitlenmeden 0.8 saniyede algılar
    # ------------------------------------------------------------

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
        try:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
        except Exception:
            pass

        print("[SİSTEM]: Mikrofon hazır. Dinliyorum...")

        print("[SİSTEM]: Mikrofon hazır. Dinliyorum...")

    while True:
        # 🔥 ULTRA SIZDIRMAZ KORUMA
        if asistan_ses.is_speaking.is_set():
            time.sleep(0.2)
            continue

        soru = ""

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=None, phrase_time_limit=None)
                if asistan_ses.is_speaking.is_set(): continue
                komut = recognizer.recognize_google(audio, language="tr-TR").strip()

            if not komut: continue
            if len(komut.strip()) <= 2 and komut.lower() not in ["ne", "ye", "al", "bak"]: continue

            print(f"[KULLANICI - HAM]: {komut}")

            # 1. ADIM: Wake Word Kontrolü (Soru değişkenini burada kesinleştiriyoruz)
            wake_word_var = wake_word_matches(komut)
            if wake_word_var and is_wake_word_only(komut):
                asistan_ses.konus(f"{profil_store.get_preferred_name()}, dinliyorum.", bekle=True)
                with sr.Microphone() as soru_source:
                    recognizer.adjust_for_ambient_noise(soru_source, duration=0.5)
                    soru_audio = recognizer.listen(soru_source, timeout=5, phrase_time_limit=None)
                    soru = recognizer.recognize_google(soru_audio, language="tr-TR").strip()
            else:
                soru = komut # Wake word yoksa komut direkt soru oluyor

            # 2. ADIM: Boşluk kontrolü
            if not soru or soru.strip() == "":
                print("[SİSTEM]: Boş komut algılandı, dinlemeye devam...")
                continue

            print(f"[KULLANICI]: {soru}")

            # 3. ADIM: Otopilot Kontrolü (Router'dan önce)
            soru_lower = soru.lower()
            bulunan_hedef = None
            for anahtar, hedef_adi in otopilot_hedefler.items():
                if anahtar in soru_lower:
                    bulunan_hedef = hedef_adi
                    break
            
            # ... (Önceki kodlar)
            
            if bulunan_hedef:
                print(f"[SİSTEM]: Otopilot hedefi algılandı -> {bulunan_hedef}")
                asistan_ses.konus(f"{bulunan_hedef} rotası hesaplandı, yola çıkıyorum.", bekle=True)
                
                # --- İŞTE BU BLOĞU BURAYA EKLE ---
                try:
                    udp_hedef_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    # Unity'nin dinlediği port 6051'e gönderiyoruz
                    udp_hedef_sock.sendto(f"{bulunan_hedef}".encode('utf-8'), ("127.0.0.1", 6051))
                    udp_hedef_sock.close()
                    print(f"[SİSTEM]: Unity'ye hedef gönderildi: {bulunan_hedef}")
                except Exception as e:
                    print(f"[HATA]: Otopilot sinyali Unity'ye gönderilemedi: {e}")
                # ---------------------------------
                
                continue # Hedef belirlendiği için döngünün başına dön
            
            # ... (router.route(komut) gibi diğer kodlar aşağıda devam eder)
            route = router.route(komut)
            
            if not soru or soru.strip() == "":
                print("[SİSTEM]: Boş komut algılandı, dinlemeye devam...")
                continue

            print(f"[KULLANICI]: {soru}")

            # ======= 🔥 HAKAN'IN OTOPİLOT NİYET KONTROLÜ 🔥 =======
            soru_lower = soru.lower()
            bulunan_hedef = None
            
            # Burada 'otopilot_hedefler' sözlüğünü main() içinde tanımlamış olmalısın
            for anahtar, hedef_adi in otopilot_hedefler.items():
                if anahtar in soru_lower:
                    bulunan_hedef = hedef_adi
                    break
            
            if bulunan_hedef:
                print(f"[SİSTEM]: Otopilot hedefi algılandı -> {bulunan_hedef}")
                asistan_ses.konus(f"{bulunan_hedef} rotası hesaplandı, yola çıkıyorum.", bekle=True)
                try:
                    udp_hedef_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    udp_hedef_sock.sendto(f"HEDEF: {bulunan_hedef}".encode('utf-8'), ("127.0.0.1", 6051))
                    udp_hedef_sock.close()
                except Exception as e:
                    print(f"[HATA]: Otopilot sinyali gönderilemedi: {e}")
                continue

            # ======= HAKAN'IN SIZDIRMAZ GÖREV KİLİDİ MAKSİMUM SEVİYE =======
            soru_lower = soru.lower()
            gorsel_kelimeler = ["betimle", "ne var", "karşımda", "karsimda", "görüyorsun", "goruyorsun", "bak", "oda", "konumu"]
            navigasyon_kelimeler = ["götür", "gotur", "tarif", "nasıl giderim", "nasil giderim", "yol göster", "gitmek istiyorum", "götürür müsün"]

            # Eğer soruda bu kritik kelimelerden biri bile geçiyorsa ROUTER'A HİÇ BAKMA, DİREKT VİZYONA SOK!
            is_gorsel = any(k in soru_lower for k in gorsel_kelimeler)
            is_navigasyon = any(k in soru_lower for k in navigasyon_kelimeler)
            

            # ======= 🔥 HAKAN'IN SIZDIRMAZ GÖREV KİLİDİ =======
            if is_gorsel or is_navigasyon:
                print(f"[ZORUNLU GÖREV TETİKLENDİ]: Niyet 'VISION' olarak kilitlendi.")
                with kilid:
                    kare_kopyasi = son_kare.copy() if son_kare is not None else None
                    giden_radar = anlik_radar
                    giden_pusula = anlik_pusula # Unity'den gelen taze pusula verisi

                if kare_kopyasi is not None:
                    # Pusula verisini fonksiyona gönderiyoruz
                    yanit = run_visual_reply(
                        beyin, gozu, asistan_ses, soru, kare_kopyasi, 
                        profil_store, mevcut_konum, giden_radar, spatial_store, giden_pusula
                    )
                    konusma_gecmisi.append(f"Kullanıcı: {soru}")
                    konusma_gecmisi.append(f"Asistan: {yanit}")
                else:
                    asistan_ses.konus("Kamera görüntüsü yükleniyor, lütfen bekleyin.", bekle=True)
                continue
            # ======================================================================

            # --- DİĞER STANDART NİYETLER (Sadece yukarıdaki kelimeler geçmiyorsa çalışır) ---
            if route.intent == "name_change":
                guncel_profil = profil_store.update_from_text(soru)
                yeni_isim = guncel_profil["preferred_name"]
                yanit = f"Tamam {yeni_isim}, bundan sonra sana böyle sesleneceğim."
                konusma_gecmisi.append(f"Kullanıcı: {soru}")
                konusma_gecmisi.append(f"Asistan: {yanit}")
                asistan_ses.konus(yanit, bekle=True)
                continue

            elif route.intent == "weather":
                guncel_profil = profil_store.update_from_text(soru)
                sehir = guncel_profil["city"]
                hava_bilgisi = weather_service.get_weather_text(sehir)
                konusma_gecmisi.append(f"Kullanıcı: {soru}")
                konusma_gecmisi.append(f"Asistan: {hava_bilgisi}")
                print(f"[ASİSTAN - HAVA]: {hava_bilgisi}")
                asistan_ses.konus(hava_bilgisi, bekle=True)
                continue

            elif route.intent == "internet_search":
                asistan_ses.konus("İnternetten güncel bilgileri araştırıyorum, lütfen bekleyin.", bekle=False)
                yanit = beyin.internette_ara_ve_cevapla(soru, profil_store.describe())
                duzgun_cevap = " ".join((yanit or "").split())
                print(f"[ASİSTAN - İNTERNET]: {duzgun_cevap}")
                asistan_ses.konus(duzgun_cevap, bekle=True)
                konusma_gecmisi.append(f"Kullanıcı: {soru}")
                konusma_gecmisi.append(f"Asistan: {duzgun_cevap}")
                continue

            else:
                # Yukarıdakilerin hiçbiri değilse normal havadan sudan sohbet
                yanit = run_text_reply(beyin, asistan_ses, soru, profil_store, konusma_gecmisi)
                konusma_gecmisi.append(f"Kullanıcı: {soru}")
                konusma_gecmisi.append(f"Asistan: {yanit}")
                continue

        except sr.WaitTimeoutError:
            continue
        except sr.UnknownValueError:
            continue
        except Exception as e:
            print(f"[DEBUG - SESSİZ DÖNGÜ]: {e}")
            continue


if __name__ == "__main__":
    main()