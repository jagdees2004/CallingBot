import asyncio
import sys

# CRITICAL WINDOWS FIX: Prevent DuplexClosed/Proactor errors
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

print("\n--- AGENT STARTING ---\n", flush=True)

import os
import certifi
import json
import csv
import logging
from datetime import datetime
from dotenv import load_dotenv

# Fix for SSL
os.environ['SSL_CERT_FILE'] = certifi.where()

from livekit import agents, api
from livekit.agents import AgentSession, Agent
from livekit.plugins import openai, silero, deepgram
from livekit.agents import llm
from typing import Annotated

# Load env
load_dotenv(".env")

# Basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound-agent")

import config

class TransferFunctions(llm.ToolContext):
    def __init__(self, ctx: agents.JobContext, phone_number: str = None):
        super().__init__(tools=[])
        self.ctx = ctx
        self.phone_number = phone_number
        self.done_event = asyncio.Event()

    def _signal_done(self):
        """Idempotent signaling helper."""
        if not self.done_event.is_set():
            self.done_event.set()

    @llm.function_tool(description="Save lead information when user is interested")
    async def save_lead(self, 
                  status: Annotated[str, "The result of the interaction (e.g. 'interested')"] = "interested"):
        """Record the phone number, date and time of the lead."""
        phone = self.phone_number or "Unknown"
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        
        try:
            file_path = "leads.csv"
            file_exists = os.path.isfile(file_path)
            
            def write_csv():
                with open(file_path, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["Phone Number", "Date", "Time"])
                    writer.writerow([phone, date_str, time_str])
            
            await asyncio.to_thread(write_csv)
            
            print(f"DEBUG: Lead saved for {phone}. Status: {status}", flush=True)
            self._signal_done()
            return {"status": "success", "message": "Lead saved successfully."}
        except Exception as e:
            print(f"DEBUG ERROR saving lead: {e}", flush=True)
            return {"status": "error", "message": str(e)}

    @llm.function_tool(description="End the call immediately")
    async def end_call(self, reason: Annotated[str, "The reason for ending the call"] = "completed"):
        """Signal that the call should end."""
        print(f"DEBUG: end_call tool called. Reason: {reason}", flush=True)
        self._signal_done()
        return {"status": "ending", "reason": reason}

async def entrypoint(ctx: agents.JobContext):
    print(f"DEBUG: --- Entrypoint started for room {ctx.room.name} ---", flush=True)
    
    phone_number = None
    try:
        if ctx.job.metadata:
            phone_number = json.loads(ctx.job.metadata).get("phone_number")
            print(f"DEBUG: Target phone: {phone_number}", flush=True)
    except: pass

    fnc_ctx = TransferFunctions(ctx, phone_number)

    # Standardizing on Deepgram + Groq
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2-phonecall", language="en"), 
        llm=openai.LLM(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
            model=config.GROQ_MODEL,
        ),
        tts=deepgram.TTS(model="aura-asteria-en"),
    )

    @session.on("transcript_finished")
    def on_transcript(transcript: agents.stt.SpeechEvent):
        if transcript.alternatives:
            print(f"DEBUG STT: {transcript.alternatives[0].text}", flush=True)

    print("DEBUG: Starting session engine...", flush=True)
    agent = Agent(instructions=config.SYSTEM_PROMPT, tools=list(fnc_ctx.function_tools.values()))
    await session.start(room=ctx.room, agent=agent)
    print("DEBUG: Session live. Waiting for connection...", flush=True)

    if phone_number:
        print(f"DEBUG: Dialing SIP to {phone_number}...", flush=True)
        try:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=config.SIP_TRUNK_ID,
                    sip_call_to=phone_number,
                    participant_identity=f"sip_{phone_number}",
                    wait_until_answered=True,
                )
            )
            print("DEBUG: Connected! Waiting for audio stream...", flush=True)
            await asyncio.sleep(2)
            
            # GREETING BARRIER
            print(f"DEBUG: Speaking greeting: {config.INITIAL_GREETING}", flush=True)
            greeting_started = asyncio.Event()
            await session.say(config.INITIAL_GREETING, allow_interruptions=True)
            greeting_started.set()
            
            # DETERMINISTIC LIFECYCLE MONITOR
            # Wait for both greeting to start AND the LLM completion signal
            await greeting_started.wait()
            await fnc_ctx.done_event.wait()
            
            print(f"\n{'='*50}", flush=True)
            print(f"!!! LIFECYCLE SIGNAL RECEIVED: Ending Call !!!", flush=True)
            print(f"{'='*50}\n", flush=True)
            
            # The "Golden Sequence"
            print("DEBUG: Speaking final goodbye...", flush=True)
            await session.say(
                "Thank you. Our team will reach you soon. Goodbye!", 
                allow_interruptions=False
            )
            
            print("DEBUG: Flushing audio buffer (1.5s)...", flush=True)
            await asyncio.sleep(1.5)
            
            print("--- CLOSING SESSION ---", flush=True)
            await session.aclose()
            return 
            
        except Exception as e:
            logger.exception("Dial/session error")
            try:
                await session.aclose()
            except Exception:
                pass
    else:
        print("DEBUG: No phone number. Waiting for fallback...", flush=True)
        await session.say(config.fallback_greeting, allow_interruptions=True)

if __name__ == "__main__":
    from livekit.agents import cli
    cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-agent", 
        )
    )
