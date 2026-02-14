import asyncio
import sys
import os
import certifi
import json
import logging
import aiohttp
import io
import wave
import csv
import math
import struct
from datetime import datetime
from dotenv import load_dotenv

# LiveKit Imports
from livekit import agents, api, rtc
from livekit.plugins import silero, openai
from livekit.agents import vad

# Local Config
import config

# ================= SYSTEM SETUP ================= #
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

os.environ["SSL_CERT_FILE"] = certifi.where()
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("voice-agent")


# ================= CALL SESSION CLASS ================= #
class CallSession:
    def __init__(self, ctx: agents.JobContext, phone_number: str):
        self.ctx = ctx
        self.phone_number = phone_number
        self.sip_identity = f"sip_{phone_number}" if phone_number else None

        # State
        self.shutdown_event = asyncio.Event()
        self.listening = False
        self.http_session = None
        self.vad_task = None
        self.attempt_count = 0  # Track unclear responses

        # VAD (synchronous load)
        self.vad_plugin = silero.VAD.load(min_silence_duration=0.5)

        # Audio output
        self.audio_source = rtc.AudioSource(24000, 1)
        self.audio_track = rtc.LocalAudioTrack.create_audio_track("agent-voice", self.audio_source)

        # TTS (Kokoro via OpenAI-compatible API)
        self.tts = openai.TTS(
            base_url=config.KOKORO_URL,
            api_key="not-needed",
            model=config.KOKORO_MODEL,
            voice=config.KOKORO_VOICE,
        )

    async def start(self):
        """Main execution flow."""
        timeout = aiohttp.ClientTimeout(total=config.HTTP_TIMEOUT)
        self.http_session = aiohttp.ClientSession(timeout=timeout)
        logger.info(f"🚀 Starting session | Room: {self.ctx.room.name} | Phone: {self.phone_number}")

        try:
            # 1. Publish agent audio track
            await self.ctx.room.local_participant.publish_track(
                self.audio_track,
                rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            )

            # 2. Listen for incoming audio
            @self.ctx.room.on("track_subscribed")
            def on_track_subscribed(track, publication, participant):
                if track.kind == rtc.TrackKind.KIND_AUDIO:
                    logger.info("✅ Participant audio connected — starting VAD")
                    self.vad_task = asyncio.create_task(self.run_vad_loop(track))

            # 3. Dial
            if self.phone_number:
                await self.dial_participant()
            else:
                logger.error("❌ No phone number provided!")
                self.shutdown_event.set()

            # 4. Wait for call to finish
            await self.shutdown_event.wait()

        except Exception as e:
            logger.error(f"💥 Critical error: {e}")
        finally:
            await self.cleanup()

    async def dial_participant(self):
        """Place the outbound SIP call."""
        try:
            logger.info(f"☎️ Dialing {self.phone_number}...")
            await self.ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=self.ctx.room.name,
                    sip_trunk_id=config.SIP_TRUNK_ID,
                    sip_call_to=self.phone_number,
                    participant_identity=self.sip_identity,
                    wait_until_answered=True,
                )
            )
            logger.info("📞 Call answered! Delivering greeting...")
            await self.say(config.INITIAL_GREETING)

            # Start listening AFTER greeting finishes
            self.listening = True
            logger.info("👂 Listening for response...")

        except Exception as e:
            logger.error(f"❌ Dialing failed: {e}")
            self.shutdown_event.set()

    # ================= VAD LOOP ================= #
    async def run_vad_loop(self, track: rtc.AudioTrack):
        """Voice Activity Detection — split into two concurrent tasks to avoid deadlock."""
        audio_stream = rtc.AudioStream(track)
        vad_stream = self.vad_plugin.stream()
        self._speech_buffer = []

        # Task 1: Push audio frames into VAD
        async def push_frames():
            frame_count = 0
            try:
                async for event in audio_stream:
                    if self.shutdown_event.is_set():
                        break
                    
                    # Audio energy monitor (every ~1s)
                    frame_count += 1
                    if self.listening and frame_count % 100 == 0:
                        try:
                            pcm = event.frame.data.tobytes()
                            shorts = struct.unpack(f"{len(pcm)//2}h", pcm)
                            rms = math.sqrt(sum(s**2 for s in shorts) / len(shorts))
                            if rms > 100:
                                logger.info(f"🔊 Audio energy: {rms:.0f}")
                        except Exception:
                            pass

                    vad_stream.push_frame(event.frame)
                    if self.listening:
                        self._speech_buffer.append(event.frame)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Frame push error: {e}")
            finally:
                vad_stream.end_input()

        # Task 2: Read VAD events
        async def read_vad_events():
            try:
                async for vad_event in vad_stream:
                    if self.shutdown_event.is_set():
                        break

                    if vad_event.type == vad.VADEventType.START_OF_SPEECH:
                        self._speech_buffer = self._speech_buffer[-10:]
                        logger.info("🗣️ Speech detected...")

                    elif vad_event.type == vad.VADEventType.END_OF_SPEECH:
                        if not self._speech_buffer or not self.listening:
                            continue

                        self.listening = False
                        logger.info("🤫 Speech ended — processing...")

                        raw_pcm = b"".join(f.data.tobytes() for f in self._speech_buffer)
                        self._speech_buffer = []
                        asyncio.create_task(self.handle_response(raw_pcm))
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"VAD event error: {e}")

        # Run both concurrently
        push_task = asyncio.create_task(push_frames())
        event_task = asyncio.create_task(read_vad_events())
        
        try:
            await asyncio.gather(push_task, event_task)
        except Exception as e:
            logger.error(f"VAD loop error: {e}")
            push_task.cancel()
            event_task.cancel()

    # ================= RESPONSE HANDLING ================= #
    async def handle_response(self, audio_bytes: bytes):
        """Transcribe speech → Classify intent → Act."""

        # Step 1: Transcribe with Whisper
        text = await self.transcribe(audio_bytes)
        logger.info(f"📝 Transcribed: '{text}'")

        if not text or len(text.strip()) < 2:
            logger.info("🤷 Empty/noise — resuming listening")
            self.listening = True
            return

        # Step 2: Try keyword matching first (fast & reliable for clear yes/no)
        intent = self._keyword_classify(text)
        if intent != "unclear":
            logger.info(f"🔑 Keyword Intent: '{intent}'")
        else:
            # Step 3: Only use LLM for ambiguous text
            logger.info(f"🔑 Keywords unclear — asking LLM...")
            intent = await self._llm_classify(text)
            logger.info(f"🧠 LLM Intent: '{intent}'")

        # Step 4: Act on intent
        if intent == "interested":
            logger.info("🎉 User is INTERESTED!")
            self.save_lead("INTERESTED")
            await self.say(config.MESSAGE_INTERESTED)
            self.shutdown_event.set()

        elif intent == "not_interested":
            logger.info("⛔ User is NOT interested")
            self.save_lead("NOT INTERESTED")
            await self.say(config.MESSAGE_NOT_INTERESTED)
            self.shutdown_event.set()

        else:
            # Unclear — ask again (max 3 retries)
            self.attempt_count += 1
            if self.attempt_count >= 3:
                logger.info("😕 Max retries reached — ending call")
                await self.say(config.MESSAGE_NOT_INTERESTED)
                self.shutdown_event.set()
            else:
                logger.info(f"❓ Unclear (attempt {self.attempt_count}/3) — asking again")
                await self.say(config.MESSAGE_UNCLEAR)
                self.listening = True

    # ================= INTENT CLASSIFICATION ================= #
    @staticmethod
    def _keyword_classify(text: str) -> str:
        """Fast keyword matching — handles clear yes/no responses reliably."""
        t = text.lower().strip().replace(".", "").replace("!", "").replace(",", "")
        
        # Check negative first (since "not interested" contains "interested")
        neg = ["no", "nope", "nah", "bye", "not interested", "busy", "don't", "dont", 
               "not now", "no thanks", "no thank", "stop", "hang up", "go away"]
        if any(w in t for w in neg):
            return "not_interested"
        
        pos = ["yes", "yeah", "yep", "yup", "sure", "ok", "okay", "interested", 
               "tell me", "go ahead", "why not", "sounds good", "haan", "ha", "ji"]
        if any(w in t for w in pos):
            return "interested"
        
        return "unclear"

    async def _llm_classify(self, user_text: str) -> str:
        """Use Ollama LLM for ambiguous text that keywords can't handle."""
        try:
            payload = {
                "model": config.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": config.SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                "temperature": 0.0,
                "max_tokens": 10,
            }

            async with self.http_session.post(
                f"{config.OLLAMA_URL}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    reply = result["choices"][0]["message"]["content"].strip().lower()
                    logger.info(f"🧠 LLM raw reply: '{reply}'")
                    
                    # Parse LLM output
                    if "not_interested" in reply or "not interested" in reply:
                        return "not_interested"
                    elif "interested" in reply:
                        return "interested"
                    elif "unclear" in reply:
                        return "unclear"
                    else:
                        return "unclear"
                else:
                    body = await resp.text()
                    logger.warning(f"Ollama error {resp.status}: {body[:200]}")
                    return "unclear"

        except asyncio.TimeoutError:
            logger.error("⏰ Ollama timeout")
            return "unclear"
        except Exception as e:
            logger.error(f"Ollama exception: {e}")
            return "unclear"

    # ================= AI SERVICE CALLS ================= #
    async def transcribe(self, audio_bytes: bytes) -> str:
        """Send audio to Whisper for transcription."""
        try:
            # Convert raw PCM to WAV
            with io.BytesIO() as wav_io:
                with wave.open(wav_io, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(48000)
                    wav_file.writeframes(audio_bytes)
                wav_data = wav_io.getvalue()

            data = aiohttp.FormData()
            data.add_field("file", wav_data, filename="audio.wav", content_type="audio/wav")
            data.add_field("model", config.WHISPER_MODEL)

            async with self.http_session.post(
                f"{config.WHISPER_URL}/audio/transcriptions", data=data
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("text", "")
                else:
                    body = await resp.text()
                    logger.warning(f"Whisper error {resp.status}: {body[:200]}")
                    return ""
        except asyncio.TimeoutError:
            logger.error("⏰ Whisper timeout — is the service running?")
            return ""
        except Exception as e:
            logger.error(f"Whisper exception: {e}")
            return ""
        return "unclear"

    # ================= TTS ================= #
    async def say(self, text: str):
        """Speak text using Kokoro TTS."""
        logger.info(f"🤖 Speaking: {text}")
        try:
            async for chunk in self.tts.synthesize(text):
                await self.audio_source.capture_frame(chunk.frame)
        except Exception as e:
            logger.error(f"TTS error: {e}")

    # ================= LEAD STORAGE ================= #
    def save_lead(self, status: str):
        """Save lead to CSV file."""
        try:
            filename = "lead.csv"
            file_exists = os.path.isfile(filename)
            with open(filename, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Phone Number", "Status", "Date", "Time"])
                now = datetime.now()
                writer.writerow([
                    self.phone_number,
                    status,
                    now.strftime("%Y-%m-%d"),
                    now.strftime("%H:%M:%S"),
                ])
            logger.info(f"💾 Lead saved: {self.phone_number} → {status}")
        except Exception as e:
            logger.error(f"CSV save error: {e}")

    # ================= CLEANUP ================= #
    async def cleanup(self):
        """Gracefully close everything."""
        logger.info("🧹 Cleaning up session...")

        # Cancel VAD
        if self.vad_task:
            self.vad_task.cancel()
            try:
                await self.vad_task
            except asyncio.CancelledError:
                pass

        # Close HTTP
        if self.http_session:
            await self.http_session.close()

        # Remove SIP participant (hang up the phone call)
        if self.sip_identity:
            try:
                await self.ctx.api.room.remove_participant(
                    api.RoomParticipantIdentity(
                        room=self.ctx.room.name,
                        identity=self.sip_identity,
                    )
                )
            except Exception:
                pass

        self.ctx.shutdown()
        logger.info("✅ Session ended cleanly")


# ================= ENTRYPOINT ================= #
async def entrypoint(ctx: agents.JobContext):
    """Called by LiveKit when a job is dispatched to this worker."""
    await ctx.connect()

    # Extract phone number from dispatch metadata
    phone_number = None
    if ctx.job.metadata:
        try:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
        except Exception:
            pass

    if not phone_number and ctx.room.metadata:
        try:
            data = json.loads(ctx.room.metadata)
            phone_number = data.get("phone_number")
        except Exception:
            pass

    logger.info(f"✨ Entrypoint | Room: {ctx.room.name} | Phone: {phone_number}")
    session = CallSession(ctx, phone_number)
    await session.start()


if __name__ == "__main__":
    from livekit.agents import cli
    cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-agent",
        )
    )