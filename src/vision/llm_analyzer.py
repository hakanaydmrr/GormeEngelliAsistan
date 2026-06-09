from __future__ import annotations

import os
import re
import time
from PIL import Image
import requests
from google import genai
from google.genai import types
from .latency_logger import log_latency


class ZekiAnalizci:
    def __init__(self, api_key_unused):
        # --- ÇOKLU API ANAHTARI ENTEGRASYONU ---
        self.api_anahtarlari = []
        
        # 1. Öncelik: Alt tiresiz KEY1, KEY2 mimarisi
        index = 1
        while True:
            key = os.getenv(f"GEMINI_API_KEY{index}") 
            if not key:
                break
            self.api_anahtarlari.append(key)
            index += 1

        # 2. Öncelik: Alt tireli mimariyi (KEY_1) tara
        if not self.api_anahtarlari:
            index = 1
            while True:
                key = os.getenv(f"GEMINI_API_KEY_{index}")
                if not key:
                    break
                self.api_anahtarlari.append(key)
                index += 1

        # 3. Öncelik: Eski tekli anahtar
        if not self.api_anahtarlari and os.getenv("GEMINI_API_KEY"):
            self.api_anahtarlari.append(os.getenv("GEMINI_API_KEY"))

        self.aktif_key_index = 0
        
        # --- MODEL HAVUZU ---
        self.model_havuzu = ["gemini-2.5-flash", "gemini-2.0-flash"]
        self.aktif_model_index = 0
        self.model_id = self.model_havuzu[self.aktif_model_index]

        # İstemciyi başlat
        self._client_guncelle()

        self.gorsel_system_instruction = (
            "Sen görme engelli bir birey için tasarlanmış profesyonel, güvenilir ve kapsamlı bir görsel yaşam asistanı ve otonom navigatörsün. "
            "Amacın, kullanıcının çevresini anlamasını, güvende olmasını, metinleri okuyabilmesini ve bağımsız hareket edebilmesini sağlamaktır.\n\n"
            "HAYATİ KURALLAR:\n"
            "1- MİKRO-NAVİGASYON (ÇOK KRİTİK): Kullanıcı bir hedefe gitmek istediğinde ona ASLA tüm rotayı tek seferde anlatma! "
            "Sadece atması gereken İLK birkaç adımı ve varsa o anki engeli nasıl aşacağını söyle. "
            "Cümleyi mutlaka şu şekilde bitir: 'Söylediğim adımları attığında bana seslen, rotaya devam edelim.' "
            "(Not: Kullanıcı hedefe ulaştığını göremez, ancak attığı adımı sayabilir. Kullanıcının sana onay vermesi, sistemdeki donanımsal adım sensörünü simüle eder).\n"
            "2- İŞLEVSEL BETİMLEME: Navigasyon istenmiyorsa çevreyi doğrudan tarif et. 'Güzel', 'ferah' gibi soyut yorumlar ASLA yapma. Nesnelerin materyalini, boyutunu ve tam konumunu söyle.\n"
            "3- DETAY VE METİN OKUMA: Görüntüde bir fatura, etiket, ilaç kutusu veya tabela varsa, üzerindeki yazıları eksiksiz ve kelimesi kelimesine oku.\n"
            "4- GÜVENLİK: Ortamdaki potansiyel engelleri (açık kapı, yerdeki kablo, sandalye) her durumda öncelikli olarak bildir.\n"
            "5- DOĞRUDAN ANLATIM: 'Fotoğrafta...', 'Görüyorum ki...' gibi girişler yapma. Doğrudan çevredekileri anlat.\n"
            "Cümlelerin kısa, eylemsel, net ve TAM olsun. Asla yarım kelime bırakma."
        )

        self.sohbet_system_instruction = (
            "Sen görme engelli bir birey için tasarlanmış zeki, profesyonel, saygılı ve çözüm odaklı bir Türkçe yaşam asistanısın. "
            "Kullanıcıyla günlük hayatta doğal, ancak son derece güvenilir bir rehber gibi konuş.\n\n"
            "HAYATİ KURALLAR:\n"
            "1- NETLİK: Kullanıcının sorularına lafı dolandırmadan doğrudan cevap ver. Cümlelerine 'Ah', 'Keşke', 'Maalesef' gibi dramatik ifadelerle başlama.\n"
            "2- REHBERLİK: Kullanıcı bir hedefe ulaşmak veya bir görevi yapmak istiyorsa, elindeki bağlama dayanarak ona en mantıklı, kısa ve kesin adımları sun.\n"
            "3- KİŞİSELLEŞTİRME: Kullanıcının ad tercihini hatırla ve doğal bir şekilde hitap et.\n"
            "4- DÜRÜSTLÜK VE GÖRSEL YÖNLENDİRME (ÇOK ÖNEMLİ): Sen şu an SADECE SOHBET katmanındasın ve kamerayı GÖRMÜYORSUN. "
            "Kullanıcı fiziksel çevresiyle, engellerle veya yol tarifiyle ilgili bir şey sorarsa ona asla ezbere yön verme. "
            "Ona dürüstçe şu an çevreyi göremediğini belirt ve 'Etrafına bakmam veya sana yol göstermem için lütfen beni yönlendir / betimlememi iste' diyerek onu doğru görsel komutları kullanmaya teşvik et.\n"
            "Lafı uzatmadan, net, canlı ve TAM cümleler kur. Asla cümleleri eksik bırakma."
        )

    def _client_guncelle(self):
        """Aktif API indeksindeki anahtarı kullanarak Google GenAI istemcisini yeniler."""
        if self.api_anahtarlari:
            su_anki_key = self.api_anahtarlari[self.aktif_key_index]
            self.client = genai.Client(api_key=su_anki_key)
            print(f"[SİSTEM]: Bilişsel Katman Başarıyla Bağlandı. (Aktif Anahtar: {self.aktif_key_index + 1}/{len(self.api_anahtarlari)} | Model: {self.model_id})")
        else:
            print("[HATA]: Yapay zeka hafızasında geçerli bir GEMINI_API_KEY bulunamadı! Havuz boş.")

    def _model_degistir_ve_yonlendir(self, hata_mesaji: str) -> bool:
        """Hata durumunda önce modeller arası geçiş yapar, modeller tükenirse sıradaki API anahtarına zıplar."""
        print(f"\n[API HATASI]: {self.model_id} (Anahtar {self.aktif_key_index + 1}) başarısız. Detay: {hata_mesaji}")
        
        self.aktif_model_index += 1
        if self.aktif_model_index < len(self.model_havuzu):
            self.model_id = self.model_havuzu[self.aktif_model_index]
            print(f"[SİSTEM]: Aynı anahtarla yedek modele geçiliyor: {self.model_id}\n")
            return True
        
        self.aktif_model_index = 0
        self.model_id = self.model_havuzu[self.aktif_model_index]
        
        if self.api_anahtarlari and len(self.api_anahtarlari) > 1:
            self.aktif_key_index = (self.aktif_key_index + 1) % len(self.api_anahtarlari)
            print(f"\n[KOTA ROTASYONU]: Kota bitti. {self.aktif_key_index + 1}. yedek API anahtarına geçiş yapılıyor...")
            self._client_guncelle()
            return True
        
        print("[SİSTEM UYARISI]: Havuzda dönülecek başka yedek API anahtarı kalmadı!\n")
        return False

    def _cevap_gecerli_mi(self, cevap):
        temiz_cevap = " ".join(cevap.split())
        if len(temiz_cevap) < 20:
            return False
        if len(temiz_cevap.split()) < 4:
            return False
        return True

    def _prepare_image_content(self, pil_image):
        if pil_image is None:
            return None

        if isinstance(pil_image, Image.Image):
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")
            return pil_image

        if isinstance(pil_image, (bytes, bytearray)):
            return types.File(value=bytes(pil_image), mime_type="image/png")

        return pil_image

    def _extract_text(self, response):
        if not response:
            return ""
        if hasattr(response, "text") and response.text:
            return str(response.text)

        candidates = getattr(response, "candidates", None)
        if candidates:
            first = candidates[0]
            if hasattr(first, "content") and first.content:
                return str(first.content)
            if hasattr(first, "text") and first.text:
                return str(first.text)

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, str) and parsed.strip():
            return parsed

        return ""

    def _gorsel_cevabi_uret(self, soru, pil_image, temperature=0.5, max_output_tokens=3200, system_instruction=None):
        image_content = self._prepare_image_content(pil_image)
        config_ayarlari = types.GenerateContentConfig(
            system_instruction=system_instruction or self.gorsel_system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            response_mime_type="text/plain",
        )
        start_time = time.time()
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=[soru, image_content],
            config=config_ayarlari,
        )
        latency_ms = (time.time() - start_time) * 1000
        log_latency("cloud_cognitive", latency_ms, {"model_id": self.model_id, "request_type": "visual"})
        return response

    def _metin_cevabi_uret(self, soru, baglam="", temperature=0.7, max_output_tokens=3200, system_instruction=None):
        config_ayarlari = types.GenerateContentConfig(
            system_instruction=system_instruction or self.sohbet_system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            response_mime_type="text/plain",
        )
        metin = soru.strip()
        if baglam.strip():
            metin = f"{baglam.strip()}\n\nKullanıcı mesajı: {metin}"
        return self.client.models.generate_content(
            model=self.model_id,
            contents=metin,
            config=config_ayarlari,
        )

    def _internet_cevabi_uret(self, soru, baglam="", temperature=0.5, max_output_tokens=3200):
        config_ayarlari = types.GenerateContentConfig(
            system_instruction=(
                "Sen internet erişimi olan, bilgiye aç görme engelli bir kullanıcıya yardım eden zeki bir asistansın. "
                "Sana gelen soruyu, arka plandaki Google Arama aracını kullanarak en güncel web verileriyle cevapla. "
                "Bilgiyi tamamen Türkçe, doğal, akıcı and bir insan gibi harmanlayarak seslendirmeye uygun aktar."
            ),
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            response_mime_type="text/plain",
            tools=[{"google_search": {}}]
        )
        metin = soru.strip()
        if baglam.strip():
            metin = f"{baglam.strip()}\n\nKullanıcı sorusu: {metin}"
        return self.client.models.generate_content(
            model=self.model_id,
            contents=metin,
            config=config_ayarlari,
        )

    def _duckduckgo_instant_answer(self, soru: str) -> str:
        try:
            response = requests.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": soru,
                    "format": "json",
                    "no_redirect": "1",
                    "skip_disambig": "1",
                    "t": "gormeengelli-asistan"
                },
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("Answer"):
                return data["Answer"].strip()

            abstract = data.get("AbstractText", "").strip()
            if abstract:
                return abstract

            related = data.get("RelatedTopics", [])
            snippets = []
            for topic in related[:3]:
                text = topic.get("Text") or topic.get("Name")
                if text:
                    snippets.append(text.strip())
            if snippets:
                return " ".join(snippets)

            return ""
        except Exception as e:
            print(f"[DUCKDUCKGO FALLBACK HATASI]: {e}")
            return ""

    def _bing_search_fallback(self, soru: str) -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(
                "https://www.bing.com/search",
                params={"q": soru, "mkt": "tr-TR"},
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            html = response.text
            matches = re.findall(r'<li class="b_algo".*?</li>', html, flags=re.S)
            for block in matches[:6]:
                snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, flags=re.S)
                if snippet_match:
                    snippet = re.sub(r'<.*?>', '', snippet_match.group(1)).strip()
                    if len(snippet) >= 20:
                        return snippet
            for block in matches[:6]:
                title_match = re.search(r'<h2.*?<a[^>]*>(.*?)</a>', block, flags=re.S)
                if title_match:
                    title = re.sub(r'<.*?>', '', title_match.group(1)).strip()
                    if len(title) >= 20:
                        return title
            return ""
        except Exception as e:
            print(f"[BING FALLBACK HATASI]: {e}")
            return ""

    def internette_ara_ve_cevapla(self, soru, baglam=""):
        if not soru or not soru.strip():
            return "İnternette ne aratmamı istersin? Tam duyamadım."

        deneme_siniri = len(self.api_anahtarlari) * len(self.model_havuzu) * 2
        deneme = 0

        while deneme < deneme_siniri:
            try:
                response = self._internet_cevabi_uret(soru, baglam=baglam)
                cevap = self._extract_text(response).strip()
                if cevap and len(cevap.split()) >= 4:
                    return cevap
                break
            except Exception as e:
                error_msg = str(e)
                deneme += 1
                print(f"[İNTERNET API HATASI - {self.model_id}]: {error_msg}")

                if "429" in error_msg:
                    time.sleep(2)

                self._model_degistir_ve_yonlendir(error_msg)
                continue

        # Gemini canlı arama desteklemez veya yeterli sonuç vermediğinde yedek olarak DuckDuckGo ve Bing kullan.
        fallback = self._duckduckgo_instant_answer(soru)
        if fallback:
            return fallback

        bing_fallback = self._bing_search_fallback(soru)
        if bing_fallback:
            return bing_fallback

        return "Şu an canlı arama sunucularına bağlanamıyorum."

    def sohbet_et(self, soru, baglam=""):
        if not soru or not soru.strip():
            return "Bir şey kaçırdım galiba; tekrar söyler misin?"

        deneme_siniri = len(self.api_anahtarlari) * len(self.model_havuzu) * 2
        deneme = 0

        while deneme < deneme_siniri:
            try:
                response = self._metin_cevabi_uret(soru, baglam=baglam)
                if response and response.text:
                    cevap = response.text.strip()
                    if cevap:
                        return cevap
                return "Şu an aklıma net bir cevap gelmedi."
            except Exception as e:
                error_msg = str(e)
                deneme += 1
                print(f"[SOHBET API HATASI - {self.model_id}]: {error_msg}")
                
                if "429" in error_msg:
                    time.sleep(2)
                
                self._model_degistir_ve_yonlendir(error_msg)
                continue

        return "Şu an sohbet motoruna erişemiyorum; biraz sonra tekrar deneyelim."

    def analiz_et(self, pil_image, soru="Önümde ne var?", system_instruction=None):
        if pil_image is None:
            return "Görüntü verisi alınamadı."

        deneme_siniri = max(1, len(self.api_anahtarlari) * len(self.model_havuzu) * 2)
        deneme = 0

        while deneme < deneme_siniri:
            try:
                response = self._gorsel_cevabi_uret(soru, pil_image, system_instruction=system_instruction)
                cevap = self._extract_text(response).strip()
                if cevap:
                    return cevap
                return "Şu an net bir görüntü alamadım."
            except Exception as e:
                error_msg = str(e)
                deneme += 1
                print(f"[GÖRSEL API HATASI - {self.model_id}]: {error_msg}")
                
                if "429" in error_msg:
                    import time
                    time.sleep(2)
                
                self._model_degistir_ve_yonlendir(error_msg)
                continue

        return "Görsel analiz katmanında teknik bir sorun oluştu."