import threading
import queue
import time
import win32com.client  # Windows yerel COM kütüphanesi

class SesliYanit:
    def __init__(self):
        # TTS sırasında dışarıdan gelen dinleme/recognizer süreçlerini durdurmak için event
        self.is_speaking = threading.Event()

        # Queue/worker for serialized speech
        self._q = queue.Queue()
        self._worker_stop = threading.Event()

        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        print("[SİSTEM]: Yerel Windows SAPI5 (Kilitlenmesiz) Motoru Aktif.")

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
            speaker.Rate = 1  # Konuşma hızı (0 normal, 1 hafif hızlı, 2 hızlı)

            while not self._worker_stop.is_set():
                try:
                    metin, done_evt = self._q.get(timeout=0.1)
                except queue.Empty:
                    continue

                if metin:
                    try:
                        self.is_speaking.set()
                        print(f"[SES ÇIKTI]: {metin}")
                        
                        # 1: SVSFDefault modu ile sesi başlatıyoruz
                        # 2: SVSFlagsAsync (Asenkron) parametresi vermediğimiz için ses tamamen 
                        # bitene kadar bu satır Windows düzeyinde güvenle bekler ve ASLA TAKILMAZ.
                        speaker.Speak(metin, 0) 
                        
                    except Exception as e:
                        print(f"[TTS MOTOR HATASI]: {e}")
                    finally:
                        self.is_speaking.clear()
                        if done_evt is not None:
                            done_evt.set()
                        self._q.task_done()
        finally:
            pythoncom.CoUninitialize()

    def konus(self, metin, bekle: bool = False):
        if not metin or not metin.strip():
            return

        done_evt = threading.Event() if bekle else None
        self._q.put((metin, done_evt))

        if bekle and done_evt is not None:
            # Ses tamamen bitene kadar ana döngüyü güvenle kilitliyoruz
            while not done_evt.is_set():
                time.sleep(0.02)

    def stop(self):
        self._worker_stop.set()