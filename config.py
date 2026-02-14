import os
from dotenv import load_dotenv

load_dotenv()

# --- PROMPTS ---
SYSTEM_PROMPT = """
You are a helpful and professional AI Assistant from "Kickr Technology".

**Your Goal:** Introduce Kickr Technology and ask if they are interested in our services.

**IMPORTANT:** You will receive the user's spoken response. Classify their intent as one of:
- "interested" — if they say Yes, Sure, Okay, Tell me more, or show any interest
- "not_interested" — if they say No, Not interested, Busy, Don't call, Bye, or decline
- "unclear" — if you cannot determine their intent

Respond with ONLY one of these three words: interested, not_interested, unclear
Do not add any explanation or extra text.
"""

INITIAL_GREETING = "Hello, I am calling from Kickr Technology. We provide IT services including web development, mobile apps, and AI solutions. Are you interested in learning more?"

# --- AI CONFIG (Read from .env) ---
# Ollama LLM
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_URL", "http://localhost:11434/v1"))
LLM_MODEL = os.getenv("OLLAMA_MODEL", os.getenv("LLM_MODEL", "llama3.2:1b"))

# Kokoro TTS
KOKORO_URL = os.getenv("KOKORO_BASE_URL", "http://localhost:8880/v1")
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_sarah")
KOKORO_MODEL = os.getenv("KOKORO_MODEL", "kokoro")

# Whisper STT
WHISPER_URL = os.getenv("WHISPER_BASE_URL", "http://localhost:8000/v1")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")

# --- TELEPHONY ---
SIP_TRUNK_ID = os.getenv("VOBIZ_SIP_TRUNK_ID")
OUTBOUND_NUMBER = os.getenv("VOBIZ_OUTBOUND_NUMBER")

# --- MESSAGES ---
MESSAGE_INTERESTED = "That's wonderful! Our team will reach out to you shortly with more details. Thank you and have a great day!"
MESSAGE_NOT_INTERESTED = "No problem at all. Thank you for your time. Have a great day!"
MESSAGE_UNCLEAR = "I'm sorry, could you please say Yes or No?"

# --- TIMEOUTS (seconds) ---
HTTP_TIMEOUT = 30  # Local AI services can be slow on first request