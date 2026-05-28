import pyttsx3
import threading
import queue
import pythoncom
import time


class SesliYanit:
    def __init__(self):
        # TTS sırasında dışarıdan gelen dinleme/recognizer süreçlerini durdurmak için event
        self.is_speaking = threading.Event()

        # Single engine init
        self.engine = pyttsx3.init()
        self.voice_id = None
        voices = self.engine.getProperty("voices")
        for v in voices:
            if "Turkish" in v.name or "tr" in v.id.lower():
                self.voice_id = v.id
                break
        if not self.voice_id:
            self.voice_id = voices[0].id

        self.engine.setProperty("voice", self.voice_id)
        self.engine.setProperty("rate", 170)

        print(f"[SİSTEM]: Ses motoru hazır. Kullanılan Ses: {self.voice_id}")

        # Queue/worker for serialized speech
        self._q: "queue.Queue[tuple[str, threading.Event]]" = queue.Queue()
        self._worker_stop = threading.Event()

        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def _worker(self):
        # Keep COM initialized in the worker thread
        pythoncom.CoInitialize()
        try:
            while not self._worker_stop.is_set():
                try:
                    metin, done_evt = self._q.get(timeout=0.1)
                except queue.Empty:
                    continue

                try:
                    if metin:
                        self.is_speaking.set()
                        print(f"[SES ÇIKTI]: {metin}")
                        self.engine.say(metin)
                        self.engine.runAndWait()
                        self.is_speaking.clear()
                finally:
                    if done_evt is not None:
                        done_evt.set()
                    self._q.task_done()
        finally:
            pythoncom.CoUninitialize()

    def konus(self, metin, bekle: bool = False):
        if not metin:
            return

        done_evt = threading.Event() if bekle else None
        self._q.put((metin, done_evt))

        if bekle and done_evt is not None:
            # Block until this speech finishes
            while not done_evt.is_set():
                time.sleep(0.01)

    def stop(self):
        self._worker_stop.set()

