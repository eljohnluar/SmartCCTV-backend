import queue
import threading
import tempfile
import os
import time
from utils.config import settings
from utils.logger import logger

class VoiceAnnouncer:
    """
    Queue-based Text-to-Speech announcement system using gTTS.
    Prevents overlapping audio playback and runs in a separate daemon thread.
    """
    def __init__(self):
        self.message_queue = queue.Queue()
        self.is_running = True
        self.enabled = settings.VOICE_ENABLED
        self.lang = settings.VOICE_LANGUAGE
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def announce(self, message: str, priority: bool = False):
        """Enqueue speech announcement"""
        if not self.enabled:
            return
        logger.info(f"[Voice Announcer] Queued message: '{message}'")
        self.message_queue.put(message)

    def announce_student_present(self, student_name: str):
        self.announce(f"{student_name} is present")

    def announce_security_alert(self, alert_description: str):
        self.announce(f"Security alert! {alert_description}", priority=True)

    def _worker(self):
        while self.is_running:
            try:
                message = self.message_queue.get(timeout=1.0)
                self._play_tts(message)
                self.message_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in announcement worker: {e}")

    def _play_tts(self, message: str):
        tmp_path = None
        try:
            from gtts import gTTS
            tts = gTTS(text=message, lang=self.lang, slow=False)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_path = f.name
            tts.save(tmp_path)

            # Play using pygame mixer if available
            try:
                import pygame
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                pygame.mixer.music.unload()
            except Exception as play_err:
                logger.debug(f"Audio playback device unavailable or uninitialized: {play_err}")

        except ImportError:
            logger.debug(f"[TTS Simulation]: '{message}'")
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

voice_announcer = VoiceAnnouncer()
