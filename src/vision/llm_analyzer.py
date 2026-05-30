from __future__ import annotations

import os
import time
from google import genai
from google.genai import types


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

    def _cevabi_uret(self, soru, pil_image, temperature=0.5, max_output_tokens=3200):
        config_ayarlari = types.GenerateContentConfig(
            system_instruction=self.gorsel_system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        return self.client.models.generate_content(
            model=self.model_id,
            contents=[soru, pil_image],
            config=config_ayarlari,
        )

    def _metin_cevabi_uret(self, soru, baglam="", temperature=0.7, max_output_tokens=3200):
        config_ayarlari = types.GenerateContentConfig(
            system_instruction=self.sohbet_system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
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

    def internette_ara_ve_cevapla(self, soru, baglam=""):
        if not soru or not soru.strip():
            return "İnternette ne aratmamı istersin? Tam duyamadım."

        deneme_siniri = len(self.api_anahtarlari) * len(self.model_havuzu) * 2
        deneme = 0

        while deneme < deneme_siniri:
            try:
                response = self._internet_cevabi_uret(soru, baglam=baglam)
                if response and response.text:
                    cevap = response.text.strip()
                    if cevap:
                        return cevap
                return "Aradığın konuya dair internette net bir güncel veri bulamadım."
            except Exception as e:
                error_msg = str(e)
                deneme += 1
                print(f"[İNTERNET API HATASI - {self.model_id}]: {error_msg}")
                
                if "429" in error_msg:
                    time.sleep(2)
                
                self._model_degistir_ve_yonlendir(error_msg)
                continue

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

    def analiz_et(self, pil_image, soru="Önümde ne var?"):
        if pil_image is None:
            return "Görüntü verisi alınamadı."

        deneme_siniri = len(self.api_anahtarlari) * len(self.model_havuzu) * 2
        deneme = 0

        while deneme < deneme_siniri:
            try:
                response = self._cevabi_uret(soru, pil_image)
                if response and response.text:
                    # Düzeltme ve cımbızlama döngüsü iptal edildi, ham ve tam metin doğrudan döndürülüyor.
                    return response.text.strip()
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