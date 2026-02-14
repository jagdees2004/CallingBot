"""
CallingBot — AI Outbound Voice Agent
Uses LiveKit, Deepgram (STT/TTS), and Groq (Llama 3.3) for intelligent outbound calls.
All settings are configurable via .env → config.py — zero hardcoded values.
Run: python agent.py start
"""

import asyncio
import sys

# CRITICAL WINDOWS FIX — must be before any async operations
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import certifi
import json
import csv
import logging
from datetime import datetime
from dotenv import load_dotenv
from typing import Annotated

# SSL Fix
os.environ["SSL_CERT_FILE"] = certifi.where()
load_dotenv(".env")

# LiveKit Imports
from livekit import agents, api
from livekit.agents import AgentSession, Agent
from livekit.plugins import openai, silero, deepgram
from livekit.agents import llm
from livekit.protocol.room import DeleteRoomRequest

# Local Config — all values read from .env
import config

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(config.AGENT_NAME)


# ================= TOOL FUNCTIONS ================= #
class CallTools(llm.ToolContext):
    """LLM tools for saving leads and ending calls."""

    def __init__(self, ctx: agents.JobContext, phone_number: str = None):
        super().__init__(tools=[])
        self.ctx = ctx
        self.phone_number = phone_number
        self.done_event = asyncio.Event()
        self.user_interested = False

    def _signal_done(self):
        """Signal that the call should end."""
        if not self.done_event.is_set():
            self.done_event.set()

    @llm.function_tool(description="Save lead information when user is interested")
    async def save_lead(self, status: Annotated[str, "The result"] = "interested"):
        """Record the phone number, date and time of the lead."""
        phone = self.phone_number or "Unknown"
        now = datetime.now()

        try:
            file_exists = os.path.isfile(config.LEADS_FILE)

            def write_csv():
                with open(config.LEADS_FILE, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["Phone Number", "Status", "Date", "Time"])
                    writer.writerow([
                        phone,
                        status,
                        now.strftime("%Y-%m-%d"),
                        now.strftime("%H:%M:%S"),
                    ])

            await asyncio.to_thread(write_csv)
            logger.info(f"💾 Lead saved: {phone} → {status}")
            self.user_interested = True
            self._signal_done()
            return {"status": "success", "message": f"Lead saved for {phone}."}
        except Exception as e:
            logger.error(f"CSV save error: {e}")
            return {"status": "error", "message": str(e)}

    @llm.function_tool(description="End the call immediately")
    async def end_call(self, reason: Annotated[str, "Reason for ending"] = "completed"):
        """Signal that the call should end."""
        logger.info(f"📴 end_call tool invoked — reason: {reason}")
        self.user_interested = False
        self._signal_done()
        return {"status": "ending", "reason": reason}


# ================= ENTRYPOINT ================= #
async def entrypoint(ctx: agents.JobContext):
    """Called by LiveKit when a job is dispatched to this worker."""
    logger.info(f"✨ Entrypoint | Room: {ctx.room.name}")

    # Extract phone number from dispatch metadata
    phone_number = None
    try:
        if ctx.job.metadata:
            phone_number = json.loads(ctx.job.metadata).get("phone_number")
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"Failed to parse metadata: {e}")

    logger.info(f"📞 Phone: {phone_number or 'N/A'}")

    # Initialize tools and session
    call_tools = CallTools(ctx, phone_number)

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model=config.STT_MODEL, language=config.STT_LANGUAGE),
        llm=openai.LLM(
            base_url=config.LLM_BASE_URL,
            api_key=config.LLM_API_KEY,
            model=config.GROQ_MODEL,
        ),
        tts=deepgram.TTS(model=config.TTS_MODEL),
    )

    agent = Agent(
        instructions=config.SYSTEM_PROMPT,
        tools=list(call_tools.function_tools.values()),
    )

    # Start the agent session
    try:
        await session.start(room=ctx.room, agent=agent)
    except Exception as e:
        logger.error(f"Failed to start agent session: {e}")
        return

    # Outbound call flow
    if phone_number:
        logger.info(f"☎️ Dialing {phone_number}...")
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
            logger.info("📞 Call answered! Delivering greeting...")

            # Brief pause for audio to stabilize
            await asyncio.sleep(config.POST_GREETING_DELAY)

            # Deliver greeting
            await session.say(config.INITIAL_GREETING, allow_interruptions=True)

            # Wait for LLM to call save_lead or end_call
            logger.info("👂 Listening for response...")
            await call_tools.done_event.wait()

            # Speak dynamic goodbye
            if call_tools.user_interested:
                final_msg = config.MESSAGE_INTERESTED
                logger.info("🎉 User is INTERESTED!")
            else:
                final_msg = config.MESSAGE_NOT_INTERESTED
                logger.info("⛔ User is NOT interested")

            try:
                await session.say(final_msg, allow_interruptions=False)
            except Exception as e:
                logger.warning(f"TTS goodbye error: {e}")

            # Give time for audio to play
            await asyncio.sleep(config.POST_GOODBYE_DELAY)

        except Exception as e:
            logger.error(f"❌ Call failed: {e}")
        finally:
            # Clean up: delete room and close session
            try:
                await ctx.api.room.delete_room(
                    DeleteRoomRequest(room=ctx.room.name)
                )
                logger.info("🗑️ Room deleted")
            except Exception as e:
                logger.warning(f"Room delete error: {e}")

            try:
                await session.aclose()
            except Exception:
                pass
            logger.info("✅ Session ended cleanly")
    else:
        # Fallback for non-SIP sessions (e.g., browser testing)
        await session.say(config.FALLBACK_GREETING, allow_interruptions=True)


if __name__ == "__main__":
    from livekit.agents import cli

    cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=config.AGENT_NAME,
        )
    )