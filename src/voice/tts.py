import threading
import queue
import time
import win32com.client  # Windows yerel COM kütüphanesi
import winsound         # Acil durumlarda anlık BİP sesi için (Windows yerleşik)

class SesliYanit:
    def __init__(self):
        # TTS sırasında dışarıdan gelen dinleme/recognizer süreçlerini durdurmak için event
        self.is_speaking = threading.Event()

        # Queue/worker for serialized speech
        self._q = queue.Queue()
        self._worker_stop = threading.Event()

        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        print("[SİSTEM]: Yerel Windows SAPI5 (Preemption/Söz Kesme Destekli) Motoru Aktif.")

    def _worker(self):
        # Windows COM nesnelerini thread içinde güvenle çalıştırmak için alt initialize
        import pythoncom
        pythoncom.CoInitialize()
        
        try:
            # Doğrudan Windows'un kendi ses objesini yaratıyoruz (Kütüphanesiz saf SAPI5)
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            
            # Tolga sesini Windows sisteminden bulup atıyoruz
            voices = speaker.GetVoices()
            tolga_index = 0
            for i in range(voices.Count):
                v_name = voices.Item(i).GetDescription()
                if "tolga" in v_name.lower() or "turkish" in v_name.lower():
                    tolga_index = i
                    break
            speaker.Voice = voices.Item(tolga_index)
            speaker.Rate = 1  # Konuşma hızı

            while not self._worker_stop.is_set():
                try:
                    # Artık kuyruktan 3 parametre alıyoruz (metin, event, acil_mi)
                    metin, done_evt, is_acil = self._q.get(timeout=0.1)
                except queue.Empty:
                    continue

                if metin:
                    try:
                        self.is_speaking.set()
                        
                        if is_acil:
                            # 1. Acil durum BİP sesi (Kullanıcıyı anında irkiltir)
                            winsound.Beep(1500, 150)
                            
                            # 2. Etiketi temizle
                            metin = metin.replace("[ACİL]", "DİKKAT!")
                            print(f"[SES ÇIKTI - ACİL]: {metin}")
                            
                            # 3 (1 Async + 2 PurgeBeforeSpeak): O anki sesi ANINDA KESER ve yeni metni okur!
                            speaker.Speak(metin, 3)
                        else:
                            print(f"[SES ÇIKTI]: {metin}")
                            
                            # 1 (Async): Motoru kilitlemeden arka planda okumaya başlar
                            speaker.Speak(metin, 1)

                        # --- DİNAMİK BEKLEME VE SÖZ KESME KONTROLÜ ---
                        # SAPI arka planda konuşurken (RunningState == 2), biz Thread'i kilitmeyip kontrol ediyoruz:
                        while speaker.Status.RunningState == 2:
                            time.sleep(0.05)
                            # Konuşma devam ederken kuyruğa YENİ BİR ACİL MESAJ gelmiş mi diye bak:
                            if not self._q.empty():
                                next_item = self._q.queue[0]
                                if next_item[2]: # Eğer kuyruktaki sıradaki mesaj acil_mi == True ise
                                    break # Bekleme döngüsünü kır! Bir sonraki turda Purge(3) ile sesi yutacak.
                                    
                    except Exception as e:
                        print(f"[TTS MOTOR HATASI]: {e}")
                    finally:
                        # Eğer motor başka bir ACİL mesaj tarafından kesilmediyse (gerçekten bittiyse) flag'i temizle
                        if speaker.Status.RunningState != 2:
                            self.is_speaking.clear()
                            
                        if done_evt is not None:
                            done_evt.set()
                        self._q.task_done()
        finally:
            pythoncom.CoUninitialize()

    def konus(self, metin, bekle: bool = False):
        if not metin or not metin.strip():
            return

        # Mesajda acil etiketi var mı kontrol et
        is_acil = "[ACİL]" in metin

        if is_acil:
            # EĞER ACİL DURUM VARSA: Kuyrukta okunmayı bekleyen eski/gereksiz navigasyon komutlarını çöpe at!
            with self._q.mutex:
                self._q.queue.clear()

        done_evt = threading.Event() if bekle else None
        
        # Kuyruğa Acil flag'ini de ekleyerek gönderiyoruz
        self._q.put((metin, done_evt, is_acil))

        if bekle and done_evt is not None:
            # Ses tamamen bitene kadar ana döngüyü güvenle kilitliyoruz
            while not done_evt.is_set():
                time.sleep(0.02)

    def stop(self):
        self._worker_stop.set()