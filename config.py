import os
from dotenv import load_dotenv

load_dotenv()

# ================= AGENT PERSONA & PROMPTS ================= #

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", """
You are a helpful and professional AI Assistant from "Kickr Technology".

**Your Goal:** Introduce Kickr Technology and ask if they are interested in AI voice agents or automation services.

**Rules for Lead Capture (save_lead):**
- IF the user says "Yes", "Sure", "Okay", or shows interest:
  1. Call the `save_lead` tool immediately.
  2. DO NOT speak. Output ONLY the tool call.

**Rules for Ending the Call (end_call):**
- IF the conversation is over or the user is not interested:
  1. Call the `end_call` tool immediately.
  2. DO NOT speak. Output ONLY the tool call.

**Critical Instruction:**
Once you call a tool, your job is done. Do not generate any follow-up text. The system will handle the goodbye message.
""").strip()

INITIAL_GREETING = os.getenv(
    "INITIAL_GREETING",
    "Hello, I am calling from Kickr Technology. "
    "We provide IT services including web development, mobile apps, and AI solutions. "
    "Are you interested in learning more?"
)

FALLBACK_GREETING = os.getenv(
    "FALLBACK_GREETING",
    "Hello! I am the AI assistant from Kickr Technology. How can I help you today?"
)

# ================= AI MODEL SETTINGS ================= #

# LLM Provider (Groq via OpenAI-compatible API)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Deepgram STT
STT_MODEL = os.getenv("STT_MODEL", "nova-2")
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "en")

# Deepgram TTS
TTS_MODEL = os.getenv("TTS_MODEL", "aura-asteria-en")

# ================= TELEPHONY ================= #

SIP_TRUNK_ID = os.getenv("VOBIZ_SIP_TRUNK_ID")
VOBIZ_OUTBOUND_NUMBER = os.getenv("VOBIZ_OUTBOUND_NUMBER")

# ================= AGENT SETTINGS ================= #

AGENT_NAME = os.getenv("AGENT_NAME", "outbound-agent")
LEADS_FILE = os.getenv("LEADS_FILE", "leads.csv")
POST_GREETING_DELAY = float(os.getenv("POST_GREETING_DELAY", "2"))
POST_GOODBYE_DELAY = float(os.getenv("POST_GOODBYE_DELAY", "1.5"))

# ================= RESPONSE MESSAGES ================= #

MESSAGE_INTERESTED = os.getenv(
    "MESSAGE_INTERESTED",
    "That's wonderful! Our team will reach out to you shortly with more details. Thank you and have a great day!"
)
MESSAGE_NOT_INTERESTED = os.getenv(
    "MESSAGE_NOT_INTERESTED",
    "No problem at all. Thank you for your time. Have a great day!"
)
MESSAGE_UNCLEAR = os.getenv(
    "MESSAGE_UNCLEAR",
    "I'm sorry, could you please say Yes or No?"
)