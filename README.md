# 👁️ Görme Engelli Asistanı (Vision Assistant)

Bu proje, görme engelli bireylerin günlük hayatta karşılaştıkları nesneleri tanımalarına ve çevrelerini derinlemesine analiz etmelerine yardımcı olmak amacıyla geliştirilmiş yapay zeka tabanlı bir asistandır.

## 🌟 Proje Özeti
Sistem iki ana katmandan oluşur:
1.  **Refleks Katmanı (YOLOv8):** Cihaz üzerinde (local) çalışan, nesneleri anlık olarak tespit eden hızlı katman.
2.  **Bilişsel Katman (Gemini 1.5 Flash):** Nesnelerin detaylarını, metinleri ve karmaşık sahneleri anlamlandıran bulut tabanlı analiz katmanı.

## 📂 Proje Mimarisi
```text
GörmeEngelliAsistan/
├── src/
│   ├── vision/          # YOLO ve Gemini analiz modülleri
│   ├── voice/           # Sesli yanıt (TTS) modülleri
│   └── main.py          # Uygulamanın ana giriş noktası
├── models/              # Yapay zeka modelleri (.pt dosyaları)
├── secret               # API Anahtarı (GitHub'a yüklenmez!)
├── requirements.txt     # Gerekli kütüphaneler
└── README.md            # Proje dökümantasyonu

🛠️ Kurulum ve Çalıştırma
1. Kütüphaneleri Yükleyin
Önce gerekli tüm bağımlılıkları yüklemek için terminale şu komutu yazın:

Bash
pip install -r requirements.txt
2. API Anahtarını Ayarlayın
Projenin çalışması için bir Gemini API anahtarına ihtiyacınız vardır:

Google AI Studio üzerinden ücretsiz bir API anahtarı alın.

Ana dizinde secret adında (uzantısız) bir dosya oluşturun.

Aldığınız anahtarı bu dosyanın içine yapıştırın ve kaydedin.

3. Uygulamayı Başlatın
Bash
python src/main.py
🎮 Kontroller
Otomatik: YOLOv8 ekrandaki nesneleri (insan, telefon, bardak vb.) sürekli tarar.

'a' Tuşu: O anki görüntüyü dondurur ve Gemini API'ye göndererek detaylı Türkçe betimleme yapar.

'q' Tuşu: Uygulamadan güvenli bir şekilde çıkış yapar.




🛡️ Güvenlik Notu
Bu projede API anahtarları .env veya secret dosyaları aracılığıyla yönetilmektedir. .gitignore dosyası sayesinde bu hassas verilerin GitHub gibi açık platformlara sızması engellenmiştir.

Geliştirici: Hakan Akdemir
