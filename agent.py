import asyncio
import sys

# CRITICAL WINDOWS FIX
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

os.environ['SSL_CERT_FILE'] = certifi.where()

from livekit import agents, api
from livekit.agents import AgentSession, Agent
from livekit.plugins import openai, silero, deepgram
from livekit.agents import llm
from livekit.protocol.room import DeleteRoomRequest
from typing import Annotated

load_dotenv(".env")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound-agent")

import config

class TransferFunctions(llm.ToolContext):
    def __init__(self, ctx: agents.JobContext, phone_number: str = None):
        super().__init__(tools=[])
        self.ctx = ctx
        self.phone_number = phone_number
        self.done_event = asyncio.Event()
        self.user_interested = False  # Track interest

    def _signal_done(self):
        if not self.done_event.is_set():
            self.done_event.set()

    @llm.function_tool(description="Save lead information when user is interested")
    async def save_lead(self, status: Annotated[str, "The result"] = "interested"):
        """Record the phone number, date and time of the lead."""
        phone = self.phone_number or "Unknown"
        now = datetime.now()
        
        try:
            file_path = "leads.csv"
            file_exists = os.path.isfile(file_path)
            def write_csv():
                with open(file_path, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    if not file_exists: writer.writerow(["Phone Number", "Date", "Time"])
                    writer.writerow([phone, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")])
            
            await asyncio.to_thread(write_csv)
            print(f"DEBUG: Lead saved for {phone}.", flush=True)
            self.user_interested = True  # Mark as interested
            self._signal_done()
            return {"status": "success", "message": "Lead saved."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @llm.function_tool(description="End the call immediately")
    async def end_call(self, reason: Annotated[str, "Reason"] = "completed"):
        """Signal that the call should end."""
        print(f"DEBUG: end_call tool called.", flush=True)
        self.user_interested = False # Mark as NOT interested
        self._signal_done()
        return {"status": "ending", "reason": reason}

async def entrypoint(ctx: agents.JobContext):
    print(f"DEBUG: --- Entrypoint started for room {ctx.room.name} ---", flush=True)
    
    phone_number = None
    try:
        if ctx.job.metadata:
            phone_number = json.loads(ctx.job.metadata).get("phone_number")
    except: pass

    fnc_ctx = TransferFunctions(ctx, phone_number)

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

    agent = Agent(instructions=config.SYSTEM_PROMPT, tools=list(fnc_ctx.function_tools.values()))
    
    try:
        await session.start(room=ctx.room, agent=agent)
    except Exception: pass

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
            
            await asyncio.sleep(2)
            
            greeting_started = asyncio.Event()
            await session.say(config.INITIAL_GREETING, allow_interruptions=True)
            greeting_started.set()
            
            await greeting_started.wait()
            await fnc_ctx.done_event.wait()
            
            # --- DYNAMIC MESSAGE LOGIC ---
            print("DEBUG: Speaking final goodbye...", flush=True)
            if fnc_ctx.user_interested:
                final_msg = config.MESSAGE_INTERESTED
            else:
                final_msg = config.MESSAGE_NOT_INTERESTED
            
            try:
                await session.say(final_msg, allow_interruptions=False)
            except: pass
            # -----------------------------
            
            await asyncio.sleep(1.5)

            try:
                request = DeleteRoomRequest(room=ctx.room.name)
                await ctx.api.room.delete_room(request)
            except Exception as e:
                print(f"DEBUG: Error deleting room: {e}", flush=True)
            
            await session.aclose()
            return 
            
        except Exception:
            try: await session.aclose()
            except: pass
    else:
        await session.say(config.fallback_greeting, allow_interruptions=True)

if __name__ == "__main__":
    from livekit.agents import cli
    cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint, agent_name="outbound-agent"))