import asyncio
import sys
import os
import certifi
import json
import logging
import csv
from datetime import datetime
from dotenv import load_dotenv
from typing import Annotated

# Windows Fix for asyncio loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

os.environ['SSL_CERT_FILE'] = certifi.where()

from livekit import agents, api
from livekit.agents import AgentSession, Agent, llm
from livekit.plugins import openai, silero
from livekit.protocol.room import DeleteRoomRequest

import config

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

class CallActions(llm.ToolContext):
    def __init__(self, ctx: agents.JobContext, phone_number: str = None):
        super().__init__(tools=[])
        self.ctx = ctx
        self.phone_number = phone_number
        self.done_event = asyncio.Event()
        self.user_interested = False

    @llm.function_tool(description="Hang up the call immediately")
    async def hangup(self):
        """Signals that the call should end."""
        logger.info("Hangup tool triggered.")
        self.done_event.set()
        return {"status": "success", "message": "Call ending..."}

    @llm.function_tool(description="Save lead when user is interested")
    async def save_lead(self):
        """Records the lead as interested."""
        phone = self.phone_number or "Unknown"
        now = datetime.now()
        try:
            file_path = "leads.csv"
            file_exists = os.path.isfile(file_path)
            # Writing to CSV (In prod, use a DB)
            with open(file_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists: writer.writerow(["Phone Number", "Date", "Time"])
                writer.writerow([phone, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")])
            
            logger.info(f"Lead saved: {phone}")
            self.user_interested = True
            self.done_event.set() # End call after saving
            return {"status": "success", "message": "Lead saved."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

async def entrypoint(ctx: agents.JobContext):
    logger.info(f"Entrypoint: {ctx.room.name}")
    
    phone_number = None
    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
    except: pass

    fnc_ctx = CallActions(ctx, phone_number)

    # --- AI STACK SETUP ---
    # We use the OpenAI plugin for EVERYTHING because all 3 local services
    # (Ollama, Whisper, Kokoro) provide OpenAI-compatible APIs.
    session = AgentSession(
        vad=silero.VAD.load(),
        
        # STT: Whisper (Docker on localhost:8000)
        stt=openai.STT(
            base_url=config.WHISPER_URL,
            model="whisper-1",
            api_key="dummy_stt_key",  # <--- FIXED: Added dummy key
        ),
        
        # LLM: Ollama (Local on localhost:11434)
        llm=openai.LLM(
            base_url=config.OLLAMA_URL,
            model=config.LLM_MODEL,
            api_key="ollama", 
        ),
        
        # TTS: Kokoro (Docker on localhost:8880)
        tts=openai.TTS(
            base_url=config.KOKORO_URL,
            model="kokoro",
            api_key="dummy_tts_key",
            voice="af_sarah",  
        ),
    )

    agent = Agent(
        instructions=config.SYSTEM_PROMPT, 
        tools=list(fnc_ctx.function_tools.values())
    )
    
    try:
        await session.start(room=ctx.room, agent=agent)
    except Exception as e:
        logger.error(f"Failed to start session: {e}")
        return

    # --- OUTBOUND CALL LOGIC ---
    if phone_number:
        logger.info(f"Dialing {phone_number}...")
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
            
            # Start talking
            await session.say(config.INITIAL_GREETING, allow_interruptions=True)
            
            # Wait for 'hangup' or 'save_lead'
            await fnc_ctx.done_event.wait()
            
            # Final Goodbye based on interest
            final_msg = config.MESSAGE_INTERESTED if fnc_ctx.user_interested else config.MESSAGE_NOT_INTERESTED
            try:
                await session.say(final_msg)
            except: pass
            
            await asyncio.sleep(1) # Allow TTS to finish

        except Exception as e:
            logger.error(f"SIP Error: {e}")
    
    # Clean up
    logger.info("Closing room...")
    try:
        await ctx.api.room.delete_room(DeleteRoomRequest(room=ctx.room.name))
    except: pass
    await session.aclose()

if __name__ == "__main__":
    from livekit.agents import cli
    cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint, agent_name="outbound-agent"))