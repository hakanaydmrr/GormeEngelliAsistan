# TODO

- [x] (Plan onaylandı) TTS sırasında mikrofon dinlemeyi durduracak lock/event temelli mekanizma ekle
  - [x] `src/voice/tts.py`: konuşma başlat/bitti durumlarını Event ile yöneten bir API ekle
  - [x] `src/main.py`: wake word/komut dinleme öncesi TTS'nin bittiğini bekle; konuşma devam ederken dinlemeyi atla
  - [ ] Basit test/akış kontrolü: 2-3 tur konuşma (asistan -> soru -> cevap -> tekrar soru)


