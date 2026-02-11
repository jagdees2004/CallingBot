import os
from dotenv import load_dotenv

load_dotenv()

# =========================================================================================

# --- 1. AGENT PERSONA & PROMPTS ---
SYSTEM_PROMPT = """
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
"""

INITIAL_GREETING = (
    "Hello, I am calling from Kickr Technology. "
    "Are you interested in taking our services?"
)



# --- 2. SETTINGS ---
STT_MODEL = "nova-2"
STT_LANGUAGE = "en"
TTS_MODEL = "aura-asteria-en"
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- 3. TELEPHONY ---
SIP_TRUNK_ID = os.getenv("VOBIZ_SIP_TRUNK_ID")
VOBIZ_OUTBOUND_NUMBER = os.getenv("VOBIZ_OUTBOUND_NUMBER")

# ... (Keep your existing keys and settings) ...


MESSAGE_INTERESTED = "Thank you. Our team will reach you soon. Goodbye!"
MESSAGE_NOT_INTERESTED = "Thank you for your time. Have a great day!"