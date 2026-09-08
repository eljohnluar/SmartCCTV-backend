# Speaker utility wrapper for announcer
from ai_engine.voice.announcer import voice_announcer

def play_announcement(text: str):
    voice_announcer.announce(text)
