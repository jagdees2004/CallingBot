import os
from dotenv import load_dotenv

load_dotenv()

# --- PROMPTS ---
SYSTEM_PROMPT = """
You are a helpful and professional AI Assistant from "Kickr Technology".

**Your Goal:** Introduce Kickr Technology and ask if they are interested our  services.

**Rules for Lead Capture (save_lead):**
- IF the user says "Yes", "Sure", "Okay", or shows interest:
  1. Call the `save_lead` tool immediately.
  2. DO NOT speak. Output ONLY the tool call.

**Rules for Hanging Up (hangup):**
- IF the conversation is over, the user says "No", or is not interested:
  1. Say a polite goodbye.
  2. Call the `hangup` tool immediately.

**Critical Instruction:**
Once you call a tool, your job is done. Do not generate any follow-up text.
"""

INITIAL_GREETING = "Hello, I am calling from Kickr Technology. Are you interested in our  services?"

# --- AI CONFIG (Must match .env) ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b")

# Note: We add /v1 here to ensure compatibility with the OpenAI plugin
WHISPER_URL = os.getenv("WHISPER_URL", "http://localhost:8000/v1")
KOKORO_URL = os.getenv("KOKORO_URL", "http://localhost:8880/v1")

# --- TELEPHONY ---
SIP_TRUNK_ID = os.getenv("VOBIZ_SIP_TRUNK_ID")
OUTBOUND_NUMBER = os.getenv("VOBIZ_OUTBOUND_NUMBER")

# --- MESSAGES ---
MESSAGE_INTERESTED = "Thank you. Our team will reach you soon. Goodbye!"
MESSAGE_NOT_INTERESTED = "Thank you for your time. Have a great day!"