"""Voice-note transcription via Groq Whisper — WhatsApp-bot counterpart to
the main app's utils/voice.py. Same model and no-language auto-detect
pattern, adapted to take raw downloaded audio bytes instead of an
st.audio_input UploadedFile (the bot runs as its own service and doesn't
share a process with the Streamlit app)."""
import os
from groq import Groq

WHISPER_MODEL = "whisper-large-v3-turbo"


def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "voice_note.ogg"):
    """Transcribes raw audio bytes via Groq's Whisper endpoint.

    Returns the transcript text (str), or None if there was no audio, no
    API key, or the transcription call failed.
    """
    if not audio_bytes:
        return None

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        client = Groq(api_key=api_key)
        # No `language` param — let Whisper auto-detect, since users mix
        # English/Hindi/Punjabi in one sentence.
        resp = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=WHISPER_MODEL,
        )
        text = (resp.text or "").strip()
        return text or None
    except Exception:
        return None
