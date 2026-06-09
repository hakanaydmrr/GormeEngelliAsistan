import cv2
import math
import re
import numpy as np
import socket
import threading
import time
import speech_recognition as sr
from PIL import Image
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict

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

class ObstacleFilter:
    """
    Engel bildirimlerini uzamsal (ROI) ve zamansal (Debounce) olarak filtreler.
    Memory: Aktif engel sayısı kadar O(N). Time: O(1) per check.
    """
    def __init__(self, debounce_time: float = 4.0, max_distance: float = 1.5, fov_angle: float = 30.0):
        self.debounce_time = debounce_time
        self.max_distance = max_distance
        self.fov_angle = fov_angle
        self._last_warning_times: Dict[str, float] = {}

    def should_warn(self, obj_id: str, distance: float, angle: float) -> bool:
        # 1. Uzamsal Filtre: Hedef uzakta veya yürüme konisi dışındaysa yoksay.
        if distance > self.max_distance or abs(angle) > self.fov_angle:
            return False

        current_time = time.time()
        last_time = self._last_warning_times.get(obj_id, 0.0)

        if (current_time - last_time) >= self.debounce_time:
            self._last_warning_times[obj_id] = current_time
            return True

        return False


def estimate_distance_from_area(area_ratio: float, reference_scale: float = 0.60) -> float:
    if area_ratio <= 0:
        return float("inf")
    return max(0.1, reference_scale / math.sqrt(area_ratio))


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
    import re # Virgül ve sayı temizlemek için
    
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"[SİSTEM]: Unity UDP dinleyicisi başlatıldı: {UDP_IP}:{UDP_PORT}")

    KRITIK_ENGELLER = {"chair", "table", "desk", "box", "bed", "toilet", "door"}
    son_okunan_spiker = "" 
    son_okuma_zamani = 0
    cooldown_suresi = 3.0

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
                    anlik_pusula = gelen_spiker.strip()
                    
                    yasakli_kelimeler = ["rota yok", "yönlendiriyorum", "hedefe yönlendir", "bekleniyor"]
                    
                    if not any(yasak in anlik_pusula.lower() for yasak in yasakli_kelimeler):
                        temiz_pusula = normalize_tr(anlik_pusula)
                        temiz_son_okunan = normalize_tr(son_okunan_spiker)
                        su_an = time.time()
                        zaman_farki = su_an - son_okuma_zamani
                        
                        is_acil_durum = "DİKKAT" in anlik_pusula
                        
                        # Cümle iskeletinden sayıları VE virgülleri temizliyoruz ("1,1" -> "")
                        iskelet_anlik = re.sub(r'[\d\,\.]', '', temiz_pusula).strip()
                        iskelet_eski = re.sub(r'[\d\,\.]', '', temiz_son_okunan).strip()
                        ayni_engel_mi = (iskelet_anlik == iskelet_eski)

                        if len(temiz_pusula) > 3:
                            if is_acil_durum:
                                if not ayni_engel_mi:
                                    # YENİ ENGEL
                                    if zaman_farki > 1.0:
                                        print(f"[REHBER - ACİL]: {anlik_pusula}")
                                        # Hata çıksa bile süre güncellensin diye ÖNCE atama yapıyoruz!
                                        son_okunan_spiker = anlik_pusula
                                        son_okuma_zamani = su_an
                                        asistan_ses.konus(anlik_pusula, bekle=False)
                                else:
                                    # AYNI ENGEL - Spam koruması için ses motorunun bitmesini bekle
                                    if zaman_farki > cooldown_suresi and not asistan_ses.is_speaking.is_set():
                                        print(f"[REHBER - GÜNCELLEME]: {anlik_pusula}")
                                        son_okunan_spiker = anlik_pusula
                                        son_okuma_zamani = su_an
                                        asistan_ses.konus(anlik_pusula, bekle=False)
                            else:
                                # NORMAL YOL TARİFİ
                                if temiz_pusula != temiz_son_okunan:
                                    if zaman_farki > cooldown_suresi and not asistan_ses.is_speaking.is_set():
                                        print(f"[REHBER]: {anlik_pusula}")
                                        son_okunan_spiker = anlik_pusula
                                        son_okuma_zamani = su_an
                                        asistan_ses.konus(anlik_pusula, bekle=False)
                    
                # Resim işleme ve YOLO
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


def is_room_description_request(soru: str) -> bool:
    text = soru.lower()
    anahtarlar = [
        "neredeyim", "nerede olduğum", "nerede olduğumu", "odayı", "odadayım", "odamı",
        "hangi oda", "bulunduğum oda", "bulunduğum odayı betimler", "bulunduğum odayı betimler misin",
        "şu an neredeyim", "neredeyim",
        # Görsel betimleme için sık kullanılan sorular
        "odada ne var", "odayı betimler misin", "odamda ne var"
    ]
    return any(k in text for k in anahtarlar)


def is_visual_information_request(soru: str) -> bool:
    text = soru.lower()
    anahtarlar = [
        "gördüğün", "ne olduğunu", "hangi nesnen", "hangi nesne", "bu ne", "ne yazıyor",
        "yazıyor", "okur musun", "metin", "okumak", "okur musun", "yazıyı",
        "anlat", "anlatır", "anlatır mısın", "betimle", "betimler misin", "betimlemesini"
    ]
    return any(k in text for k in anahtarlar)


def soruyu_zenginlestir(soru, sahne_ozeti, profil_ozeti, anlik_konum, pusula_verisi, visual_info_request: bool = False, room_request: bool = False):
    if room_request:
        return (
            "Sen 'Yaver' adlı, görme engelli bireyler için profesyonel bir görsel asistanısın."
            " Bu soruda kullanıcı bulunduğu odayı ve konumunu bilmek istiyor."
            " Lütfen gördüğün oda hakkında açık, kısa ve net bir tanım yap. Rotadan veya yönlendirmeden kaçın."
            " Cevabını şu formatta ver: 'Oturma odasındasın, sağında masa, solunda koltuk var.'"
            " 15 kelimeyi geçme.\n\n"
            f"KULLANICI VERİLERİ:\n"
            f"- Konum: {anlik_konum}\n"
            f"- Görüntüdeki Nesneler: {sahne_ozeti}\n\n"
            "REHBERLİK PROTOKOLÜ:\n"
            "1. Bu soruda rota bilgisi verme; sadece odayı, duvarları, zemini ve önemli nesnelerin yerini anlat.\n"
            "2. Eğer odayı kesin olarak belirleyebiliyorsan açıkla. Eğer emin değilsen, görsel detaylarla tahminini destekle.\n"
            "3. KISITLAMA: 15 kelimeyi geçme, ama oda tanımı yeterince açık olsun.\n"
        )
    if visual_info_request:
        return (
            "Sen 'Yaver' adlı, görme engelli bireyler için profesyonel bir görsel asistanısın."
            " Bu soruda kullanıcı çevredeki nesnelerin kimliğini, yazıları veya gördüğün görselin ne olduğunu bilmek istiyor."
            " Lütfen yalnızca bu bilgiyi ver; rota veya hedef yönlendirmesi yapma."
            " Cevabını kısa, net ve doğrudan tut.\n\n"
            f"KULLANICI VERİLERİ:\n"
            f"- Konum: {anlik_konum}\n"
            f"- Görüntüdeki Nesneler: {sahne_ozeti}\n\n"
            "REHBERLİK PROTOKOLÜ:\n"
            "1. Bu soruda rota bilgisinden kaçın. Sadece nesnelerin kimliğini veya yazıları belirt.\n"
            "2. Eğer yazı varsa tam olarak ne yazdığını söyle.\n"
            "3. Cümlelerin kısa ve görsel odaklı olsun.\n"
        )

    return (
        "Sen 'Yaver' adlı, görme engelli bireyler için NAVİGASYON ASİSTANISIN. Kullanıcıyı hedefe en kısa yoldan güvenle ulaştır.\n"
        "NESNELERİ GEREKSİZ BETİMLEME. Sadece yürümeyi engelleyecek nesneleri uyar.\n\n"
        
        f"KULLANICI VERİLERİ:\n"
        f"- Konum: {anlik_konum}\n"
        f"- Hedef Yönü (PUSULA): {pusula_verisi}\n"
        f"- Yol Üzerindeki Engeller (YOLO Tespiti): {sahne_ozeti}\n\n"
        
        "REHBERLİK PROTOKOLÜ (HAYATİ VE KESİN KURALLAR):\n"
        "1. KESİN EMİR: İlk cümlen mutlaka PUSULA VERİSİ olsun. Örn: 'Hedef sağ arka tarafında, sağa dön.'\n"
        "2. HALÜSİNASYON KİLİDİ: Eğer 'Engeller' kısmında 'Belirgin nesne tespit edilemedi.' yazıyorsa, ASLA nesne uydurma ve tahmin yapma! Sadece pusulayı söyleyip bitir.\n"
        "3. ENGEL YÖNETİMİ: Eğer gerçekten bir engel tespit edilmişse, pusula verisiyle birleştir. 'Sağa dönmelisin ama önünde koltuk var, solundan geç' de.\n"
        "4. KISITLAMA: Asla 15 kelimeyi geçme. Asla kullanıcıdan çevresini betimlemesini isteme.\n"
    )


def kisa_oda_tanimi(cevap: str) -> str:
    if not cevap:
        return cevap
    cumleler = re.split(r'(?<=[.!?])\s+', cevap.strip())
    if cumleler:
        ilk = cumleler[0].strip()
        kelimeler = ilk.split()
        if len(kelimeler) <= 18:
            return ilk
        return " ".join(kelimeler[:18]) + '.'
    kelimeler = cevap.split()
    return " ".join(kelimeler[:18]) + '.'


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
        "SENİN KİMLİĞİN: Sen, 'Yaver' adında, görme engelli bireylere rehberlik eden bir yapay zeka asistanısın.\n"
        "KESİN KURAL: Asla kullanıcıdan çevresini veya nesneleri betimlemesini isteme! Kullanıcı görme engellidir. Çevreyi görmek ve analiz etmek senin görevidir.\n"
        "Eğer kullanıcı 'döndüm', 'ilerledim', 'tamam' gibi navigasyon onayları verirse, sadece 'Anlaşıldı, bir sonraki adımı bekliyorum' veya 'Kameradan yeni rotayı kontrol ediyorum' gibi kısa onay cümleleri kur.\n"
        "Ton: sıcak, net, güven verici ve kısa."
    )

    if gecmis:
        son_mesajlar = "\n".join(gecmis[-4:])
        baglam = f"{baglam}\nSon sohbet akışı:\n{son_mesajlar}"

    return baglam

def run_text_reply(beyin, asistan_ses, soru, profil_store, gecmis):
    baglam = sohbet_baglamini_olustur(profil_store, gecmis)
    try:
        cevap = beyin.sohbet_et(soru, baglam=baglam)
        duzgun_cevap = " ".join((cevap or "").split())
    except Exception as e:
        print(f"[SOHBET HATA]: {e}")
        duzgun_cevap = "Şu an sohbete bağlanamıyorum. Lütfen biraz sonra tekrar dene."

    if not duzgun_cevap.strip():
        duzgun_cevap = "Şu an net bir cevap veremiyorum."

    print(f"[ASİSTAN - SOHBET]: {duzgun_cevap}")
    try:
        asistan_ses.konus(duzgun_cevap, bekle=True)
    except Exception as e:
        print(f"[SES MOTORU HATA]: {e}")
    return duzgun_cevap

def run_visual_reply(beyin, gozu, asistan_ses, soru, kare_kopyasi, profil_store, anlik_konum, radar_verisi, spatial_store, pusula_verisi, obstacle_filter: ObstacleFilter, nav_target: str | None = None, visual_info_request: bool = False):
    if kare_kopyasi is None:
        return "Görüntü verisi alınamadı."

    # --- 1. ADIM: ÇÖZÜNÜRLÜK VE İYİLEŞTİRME ---
    kare_kopyasi = cv2.resize(kare_kopyasi, (800, 600), interpolation=cv2.INTER_AREA)
    aydinlatilmis_kare = cv2.convertScaleAbs(kare_kopyasi, alpha=1.2, beta=40)
    keskinlestirme_matrisi = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    iyilestirilmis_kare = cv2.filter2D(aydinlatilmis_kare, -1, keskinlestirme_matrisi)

    img = Image.fromarray(cv2.cvtColor(iyilestirilmis_kare, cv2.COLOR_BGR2RGB))
    
    nesneler = gozu.nesneleri_tani(iyilestirilmis_kare)
    tahmin_edilen_oda = spatial_store.oda_tahmin_et(nesneler)
    etkin_konum = tahmin_edilen_oda or anlik_konum

    oda_talepli = is_room_description_request(soru)
    visual_info_request = visual_info_request or oda_talepli or is_visual_information_request(soru)
    soru_lower = soru.lower()
    kare_genisligi = iyilestirilmis_kare.shape[1]
    all_scene_summary = sahne_ozeti_olustur(nesneler, kare_genisligi)

    # Eğer kullanıcı 'önümde' veya 'karşımda' gibi kelimeler kullanıyorsa, öne odaklı kısa betimleme yap.
    front_request = any(k in soru_lower for k in ("önümde", "karşımda", "önümde ne", "karşımda ne", "önümde ne var", "karşımda ne var"))

    if oda_talepli:
        sahne_ozeti = all_scene_summary or "Belirgin nesne tespit edilemedi."
    else:
        risk_nesneler = []
        for nesne in nesneler:
            offset = (nesne["merkez_x"] - (kare_genisligi / 2)) / (kare_genisligi / 2)
            angle = offset * obstacle_filter.fov_angle
            distance = estimate_distance_from_area(nesne["alan_orani"])
            obj_id = f"{nesne['ad']}|{int(nesne['merkez_x'])}|{int(nesne['merkez_y'])}"

            if obstacle_filter.should_warn(obj_id, distance, angle):
                risk_nesneler.append(nesne)

        if risk_nesneler:
            risk_ozeti = sahne_ozeti_olustur(risk_nesneler, kare_genisligi)
            sahne_ozeti = f"Önünde kritik engeller: {risk_ozeti}"
        else:
            sahne_ozeti = "Önünde belirgin bir acil risk görünmüyor."

    # --- 2. ADIM: ZENGİNLEŞTİRİLMİŞ SORGULAMA (Pusula Verisi ile) ---
    sorgu = soruyu_zenginlestir(
        soru, sahne_ozeti, profil_store.describe(), etkin_konum, pusula_verisi,
        visual_info_request=visual_info_request,
        room_request=oda_talepli
    )
    
    if radar_verisi and "belirgin bir nesne yok" not in radar_verisi.lower():
        sorgu += f"\n\n[DİNAMİK RADAR VERİSİ]:\n{radar_verisi}"

    # --- 3. ADIM: ANALİZ ---
    if nav_target and not oda_talepli:
        sorgu = f"HEDEF: {nav_target}. {sorgu}"
        system_override = (
            "Sen görme engelli bir birey için mikro-navigasyon sağlayan bir asistansın. "
            "Kullanıcının hedefe ulaşması için sadece ilk birkaç adımı ver; asla tüm rotayı söyleme."
        )
    elif oda_talepli:
        system_override = (
            "Sen görme engelli bir birey için profesyonel bir görsel asistanısın. "
            "Bu soruda kullanıcı bulunduğu odayı ve mevcut konumunu anlamak istiyor. "
            "Lütfen sadece oda tanımı, çevre ve nesnelerin konumunu ver; rota veya hedef yönlendirmesi yapma."
        )
    elif visual_info_request:
        system_override = (
            "Sen görme engelli bir birey için profesyonel bir görsel asistanısın. "
            "Bu soruda kullanıcı çevredeki nesnelerin kimliğini, yazıları veya gördüğün görselin ne olduğunu bilmek istiyor. "
            "Lütfen rota veya hedef yönlendirmesi yapma."
        )
    else:
        system_override = None

    try:
        cevap = beyin.analiz_et(img, soru=sorgu, system_instruction=system_override)
    except Exception as e:
        print(f"[GÖRSEL HATA]: {e}")
        cevap = None

    duzgun_cevap = " ".join((cevap or "").split())

    if len(duzgun_cevap) < 20 or len(duzgun_cevap.split()) < 4:
        duzgun_cevap = genel_fallback_cevap(soru, sahne_ozeti)

    if oda_talepli:
        duzgun_cevap = kisa_oda_tanimi(duzgun_cevap)

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
    spatial_store = SpatialMemoryStore()
    router = IntentRouter(spatial_store=spatial_store)
    weather_service = WeatherService()
    obstacle_filter = ObstacleFilter()
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

    while True:
        # 🔥 1. KORUMA: SESSİZ TIKANMAYI TESPİT ET (DEBUG)
        if asistan_ses.is_speaking.is_set():
            time.sleep(0.2)
            continue

        soru = ""

        try:
            with sr.Microphone() as source:
                # 0.5 saniye çok uzun, gecikmeyi azaltmak için 0.2'ye çektik
                recognizer.adjust_for_ambient_noise(source, duration=0.2)
                
                # 🔥 2. KORUMA: DEADLOCK ÖNLEYİCİ (TIMEOUT)
                # timeout=3: 3 saniye hiç ses gelmezse hata verip döngüyü başa sarar (Kilitlenmeyi önler)
                # phrase_time_limit=10: Kullanıcı 10 saniyeden uzun konuşursa zorla keser
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=10)
                
                # Dinleme bittiğinde asistan araya girdiyse algılamayı iptal et
                if asistan_ses.is_speaking.is_set(): 
                    continue
                    
                komut = recognizer.recognize_google(audio, language="tr-TR").strip()

            if not komut: continue
            if len(komut.strip()) <= 2 and komut.lower() not in ["ne", "ye", "al", "bak"]: continue

            print(f"[KULLANICI - HAM]: {komut}")

            # 1. ADIM: Wake Word Kontrolü
            wake_word_var = wake_word_matches(komut)
            if wake_word_var and is_wake_word_only(komut):
                asistan_ses.konus(f"{profil_store.get_preferred_name()}, dinliyorum.", bekle=True)
                with sr.Microphone() as soru_source:
                    recognizer.adjust_for_ambient_noise(soru_source, duration=0.2)
                    # Soru için de kilitlenme önleyici ekledik
                    soru_audio = recognizer.listen(soru_source, timeout=5, phrase_time_limit=15)
                    soru = recognizer.recognize_google(soru_audio, language="tr-TR").strip()
            else:
                soru = komut

            # 2. ADIM: Boşluk kontrolü
            if not soru or soru.strip() == "":
                print("[SİSTEM]: Boş komut algılandı, dinlemeye devam...")
                continue

            print(f"[KULLANICI]: {soru}")

            # 3. ADIM: Otopilot Kontrolü (Router'dan önce)
            soru_lower = soru.lower()
            bulunan_hedef = None
            
            # Negatif kelimeler veya soru kelimeleri içeriyorsa rota komutu değildir!
            iptal_kelimeleri = ["yok", "değil", "hayır", "nerede", "yanlış", "görmüyorum"]
            is_iptal = any(k in soru_lower for k in iptal_kelimeleri)

            if not is_iptal:
                for anahtar, hedef_adi in otopilot_hedefler.items():
                    if anahtar in soru_lower:
                        # Rota komutu olduğundan emin olmak için ya cümle kısa olmalı (örn: "yatağa git") 
                        # ya da bir yönlendirme fiili içermeli
                        navigasyon_fiilleri = ["götür", "git", "yönlendir", "tarif", "istiyorum"]
                        if len(soru_lower.split()) <= 3 or any(f in soru_lower for f in navigasyon_fiilleri):
                            bulunan_hedef = hedef_adi
                            break
            
            if bulunan_hedef:
                print(f"[SİSTEM]: Otopilot hedefi algılandı -> {bulunan_hedef}")
                asistan_ses.konus(f"{bulunan_hedef} rotası hesaplandı, yola çıkıyorum.", bekle=True)
                
                try:
                    udp_hedef_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    udp_hedef_sock.sendto(f"{bulunan_hedef}".encode('utf-8'), ("127.0.0.1", 6051))
                    udp_hedef_sock.close()
                    print(f"[SİSTEM]: Unity'ye hedef gönderildi: {bulunan_hedef}")
                except Exception as e:
                    print(f"[HATA]: Otopilot sinyali Unity'ye gönderilemedi: {e}")
                
                continue # Hedef belirlendiği için döngünün başına dön
            
            # ... (router.route(soru) kullanarak gerçek kullanıcı sorusunu sınıflandırıyoruz)
            route = router.route(soru)

            soru_lower = soru.lower()
            
            # Öncelikle IntentRouter'ın kararını ve güven skorunu kontrol edelim.
            # Eğer router 'vision' olarak güçlü bir güvene sahipse (>= threshold),
            # görsel akışı zorunlu kılalım; aksi halde kelime tabanlı fallback kullanılır.
            vision_threshold = 0.80
            is_gorsel = False
            is_navigasyon = False

            suppress_fallback = False
            if hasattr(route, 'intent') and hasattr(route, 'confidence'):
                if route.intent == "vision" and route.confidence >= vision_threshold:
                    is_gorsel = True
                # Eğer router internet arama niyetiyle yüksek güven döndüyse, görsele geçme
                # ve fallback kelime kontrolünü devre dışı bırak.
                elif route.intent in {"internet_search", "weather"} and route.confidence >= 0.80:
                    is_gorsel = False
                    suppress_fallback = True

            # Fallback: basit kelime tabanlı tetikleyiciler korunsun (ancak yüksek güvenli non-vision intent'ler için atla)
            if not is_gorsel and not suppress_fallback:
                gorsel_kelimeler = [
                    "betimle", "ne var", "karşımda", "karsimda", "görüyorsun", "goruyorsun", "bak",
                    "oda", "konumu", "döndüm", "dondum", "ilerledim", "geldim", "attım",
                    "anlat", "anlatır", "anlatır mısın", "anlatmasını", "anlatır mısın"
                ]
                is_gorsel = any(k in soru_lower for k in gorsel_kelimeler)

            navigasyon_kelimeler = ["götür", "gotur", "tarif", "nasıl giderim", "nasil giderim", "yol göster", "gitmek istiyorum", "götürür müsün"]
            is_navigasyon = any(k in soru_lower for k in navigasyon_kelimeler)
            visual_info_request = is_visual_information_request(soru) or (is_gorsel and not is_navigasyon)

            # ======= 🔥 HAKAN'IN SIZDIRMAZ GÖREV KİLİDİ =======
            if is_gorsel or is_navigasyon:
                print(f"[ZORUNLU GÖREV TETİKLENDİ]: Niyet 'VISION' olarak kilitlendi.")
                with kilid:
                    kare_kopyasi = son_kare.copy() if son_kare is not None else None
                    giden_radar = anlik_radar
                    giden_pusula = anlik_pusula # Unity'den gelen taze pusula verisi

                if kare_kopyasi is not None:
                    # Pusula verisini fonksiyona gönderiyoruz
                    # Öncelikle router'ın çıkardığı hedefi kullan; yoksa anahtar eşlemeyle yedekle
                    detected_target = None
                    if is_navigasyon:
                        if hasattr(route, 'target') and route.target:
                            detected_target = route.target
                        else:
                            for anahtar, hedef_adi in otopilot_hedefler.items():
                                if anahtar in soru_lower:
                                    detected_target = hedef_adi
                                    break

                    yanit = run_visual_reply(
                        beyin, gozu, asistan_ses, soru, kare_kopyasi,
                        profil_store, mevcut_konum, giden_radar, spatial_store, giden_pusula,
                        obstacle_filter, nav_target=detected_target, visual_info_request=visual_info_request
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