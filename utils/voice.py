"""Shared voice-input helper: transcribes st.audio_input recordings via Groq Whisper.

Used by pages/1_orders.py, pages/2_production.py, and pages/3_procurement.py to
replace the old browser SpeechRecognition + iframe approach with Streamlit's
native mic widget (st.audio_input) plus server-side transcription.
"""
import os
from dotenv import load_dotenv
from groq import Groq

WHISPER_MODEL = "whisper-large-v3-turbo"


def transcribe_audio(audio_value):
    """Transcribe an st.audio_input recording via Groq's Whisper endpoint.

    Args:
        audio_value: the UploadedFile-like object returned by st.audio_input
            (None if nothing has been recorded yet).

    Returns:
        The transcript text (str), or None if there was no audio, no API key,
        or the transcription call failed.
    """
    if audio_value is None:
        return None

    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        client = Groq(api_key=api_key)
        # No `language` param — let Whisper auto-detect, since users mix
        # English/Hindi/Punjabi in one sentence.
        resp = client.audio.transcriptions.create(
            file=("audio.wav", audio_value.read()),
            model=WHISPER_MODEL,
        )
        text = (resp.text or "").strip()
        return text or None
    except Exception:
        return None
