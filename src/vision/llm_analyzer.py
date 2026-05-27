from __future__ import annotations

import time

from google import genai
from google.genai import types


class ZekiAnalizci:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model_havuzu = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        self.aktif_model_index = 0
        self.model_id = self.model_havuzu[self.aktif_model_index]

        self.gorsel_system_instruction = (
            "Sen görme engelli bir birey için profesyonel bir görsel yardımcısın. "
            "Kullanıcının sorusuna göre görüntüyü analiz et. "
            "Kısa ama TAM cümleler kur. "
            "Asla yarım kelime, tek kelime veya eksik giriş verme. "
            "Eğer görüntü net değilse bunu açıkça söyle ve cümleyi tamamla."
        )

        self.sohbet_system_instruction = (
            "Sen sıcak, zeki, esprili ama saygılı bir Türkçe asistansın. "
            "Kullanıcıyla günlük hayatta konuşur gibi doğal sohbet et. "
            "Kısa, net ve canlı cevaplar ver. "
            "Kullanıcının ad tercihini hatırla ve ona göre hitap et. "
            "Eğer kullanıcı hava durumu sorarsa elimde bağlam varsa ona göre yanıt ver; yoksa eksik bilgi olduğunu açıkça söyle. "
            "Görsel analiz gerektirmeyen sorularda görmeden gördüğünü iddia etme."
        )

        print(f"[SİSTEM]: Bilişsel Katman Stabil Modda. Aktif Model: {self.model_id}")

    def _cevap_gecerli_mi(self, cevap):
        temiz_cevap = " ".join(cevap.split())
        if len(temiz_cevap) < 20:
            return False
        if len(temiz_cevap.split()) < 4:
            return False
        return True

    def _cevabi_uret(self, soru, pil_image, temperature=0.4, max_output_tokens=160):
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

    def _metin_cevabi_uret(self, soru, baglam="", temperature=0.7, max_output_tokens=180):
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

    def sohbet_et(self, soru, baglam=""):
        if not soru or not soru.strip():
            return "Bir şey kaçırdım galiba; tekrar söyler misin?"

        while self.aktif_model_index < len(self.model_havuzu):
            self.model_id = self.model_havuzu[self.aktif_model_index]
            try:
                response = self._metin_cevabi_uret(soru, baglam=baglam)

                if response and response.text:
                    cevap = response.text.strip()
                    if cevap:
                        return cevap

                return "Şu an aklıma net bir cevap gelmedi."

            except Exception as e:
                error_msg = str(e)
                print(f"[SOHBET API HATASI - {self.model_id}]: {error_msg}")

                if "429" in error_msg:
                    print("\n[KOTA KORUMASI]: İstek sınırına ulaşıldı. 15 saniye sistem dinlendiriliyor...")
                    time.sleep(15)
                    return "Biraz yavaşlayalım; sistemin toparlanmasına kısa süre verelim."
                else:
                    print(f"\n[UYARI]: {self.model_id} hattı başarısız oldu. Sonraki yedek modele geçiliyor...")
                    self.aktif_model_index += 1

                    if self.aktif_model_index < len(self.model_havuzu):
                        continue
                    else:
                        self.aktif_model_index = 0
                        return "Şu an sohbet motoruna erişemiyorum; biraz sonra tekrar deneyelim."

        return "Teknik bir sorun oluştu."

    def analiz_et(self, pil_image, soru="Önümde ne var?"):
        if pil_image is None:
            return "Görüntü verisi alınamadı."

        while self.aktif_model_index < len(self.model_havuzu):
            self.model_id = self.model_havuzu[self.aktif_model_index]
            try:
                response = self._cevabi_uret(soru, pil_image)

                if response and response.text:
                    cevap = response.text.strip()
                    if self._cevap_gecerli_mi(cevap):
                        return cevap

                    duzeltme_sorusu = (
                        f"İlk cevap eksik kaldı: {cevap}\n"
                        "Bunu Türkçe, doğal ve tek bir TAM cümleye tamamla. "
                        "Yarım kelime kullanma. "
                        "Kullanıcıya doğrudan ne gördüğünü söyle."
                    )
                    duzeltme = self._cevabi_uret(
                        duzeltme_sorusu,
                        pil_image,
                        temperature=0.2,
                        max_output_tokens=180,
                    )
                    if duzeltme and duzeltme.text:
                        duzeltme_metni = duzeltme.text.strip()
                        if self._cevap_gecerli_mi(duzeltme_metni):
                            return duzeltme_metni

                    return "Görüntüyü net seçemedim; biraz daha yaklaşınca daha iyi yardımcı olurum."

                return "Şu an net bir görüntü alamadım."

            except Exception as e:
                error_msg = str(e)
                print(f"[API HATASI - {self.model_id}]: {error_msg}")

                if "429" in error_msg:
                    print("\n[KOTA KORUMASI]: İstek sınırına ulaşıldı. 15 saniye sistem dinlendiriliyor...")
                    time.sleep(15)
                    return "Şu an çok hızlı ilerliyoruz; sistemin dinlenmesi için biraz bekleyelim."
                else:
                    print(f"\n[UYARI]: {self.model_id} hattı başarısız oldu. Sonraki yedek modele geçiliyor...")
                    self.aktif_model_index += 1

                    if self.aktif_model_index < len(self.model_havuzu):
                        continue
                    else:
                        self.aktif_model_index = 0
                        return "Model yapılandırması veya API erişim yetkileri geçersiz. Lütfen API anahtarınızı kontrol edin."

        return "Teknik bir sorun oluştu."
