import asyncio
import sys
import os
import certifi
import json
import logging
import aiohttp
import io
import wave
from dotenv import load_dotenv

# Windows fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

os.environ["SSL_CERT_FILE"] = certifi.where()

from livekit import agents, api, rtc
from livekit.plugins import silero, openai
from livekit.agents import vad

import config

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")


# ========================= ENTRYPOINT ========================= #

async def entrypoint(ctx: agents.JobContext):

    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")

    phone_number = None
    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
    except Exception:
        pass

    vad_plugin = silero.VAD.load()

    tts = openai.TTS(
        base_url=config.KOKORO_URL,
        api_key="dummy",
        model="kokoro",
        voice="af_sarah",
    )

    done_event = asyncio.Event()
    sip_identity = None

    # ================= HANGUP FUNCTION ================= #

    async def hangup_call():
        try:
            logger.info("Initiating hangup...")
            await asyncio.sleep(0.5)  # let TTS finish

            # 1️⃣ Remove SIP participant (PRIMARY method)
            if sip_identity:
                try:
                    await ctx.api.room.remove_participant(
                        api.RoomParticipantIdentity(
                            room=ctx.room.name,
                            identity=sip_identity,
                        )
                    )
                    logger.info("SIP participant removed.")
                except Exception as e:
                    logger.warning(f"Remove participant failed: {e}")

            # 2️⃣ Backup: delete entire room
            try:
                await ctx.api.room.delete_room(
                    api.DeleteRoomRequest(
                        room=ctx.room.name,
                    )
                )
                logger.info("Room deleted successfully.")
            except Exception as e:
                logger.warning(f"Delete room failed: {e}")

        except Exception as e:
            logger.error(f"Hangup error: {e}")

    # ================= TTS FUNCTION ================= #

    async def say(text: str):
        logger.info(f"Agent: {text}")

        source = rtc.AudioSource(24000, 1)
        track = rtc.LocalAudioTrack.create_audio_track("agent-voice", source)

        publication = await ctx.room.local_participant.publish_track(
            track,
            rtc.TrackPublishOptions(
                source=rtc.TrackSource.SOURCE_MICROPHONE
            ),
        )

        try:
            async for chunk in tts.synthesize(text):
                await source.capture_frame(chunk.frame)
        finally:
            await ctx.room.local_participant.unpublish_track(
                publication.sid
            )

    # ================= WHISPER TRANSCRIPTION ================= #

    async def transcribe_audio(audio_bytes: bytes) -> str:
        try:
            with io.BytesIO() as wav_io:
                with wave.open(wav_io, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(48000)
                    wav_file.writeframes(audio_bytes)

                wav_data = wav_io.getvalue()

            url = f"{config.WHISPER_URL}/audio/transcriptions"

            data = aiohttp.FormData()
            data.add_field(
                "file",
                wav_data,
                filename="audio.wav",
                content_type="audio/wav",
            )
            data.add_field("model", "whisper-1")

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    if resp.status != 200:
                        logger.error("Whisper failed")
                        return ""
                    result = await resp.json()
                    return result.get("text", "").lower()

        except Exception as e:
            logger.error(f"Whisper error: {e}")
            return ""

    # ================= AUDIO PROCESSING ================= #

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            asyncio.create_task(process_audio(track))

    async def process_audio(track: rtc.AudioTrack):

        audio_stream = rtc.AudioStream(track)
        vad_stream = vad_plugin.stream()

        speech_buffer = []
        listening = True

        async def vad_listener():
            nonlocal speech_buffer, listening

            async for event in vad_stream:

                if event.type == vad.VADEventType.START_OF_SPEECH:
                    logger.info("User speaking...")
                    speech_buffer = []

                elif event.type == vad.VADEventType.END_OF_SPEECH:
                    logger.info("End of speech. Processing...")

                    if not speech_buffer:
                        continue

                    raw_pcm = b"".join(
                        frame.data.tobytes()
                        for frame in speech_buffer
                    )

                    speech_buffer = []

                    text = await transcribe_audio(raw_pcm)

                    if not text:
                        continue

                    logger.info(f"User: {text}")

                    if any(
                        w in text
                        for w in ["yes", "yeah", "sure", "interested"]
                    ):
                        await say(config.MESSAGE_INTERESTED)
                        await hangup_call()
                        done_event.set()
                        listening = False
                        break

                    elif any(
                        w in text
                        for w in ["no", "nope", "bye"]
                    ):
                        await say(config.MESSAGE_NOT_INTERESTED)
                        await hangup_call()
                        done_event.set()
                        listening = False
                        break

        vad_task = asyncio.create_task(vad_listener())

        async for frame_event in audio_stream:
            if not listening:
                break

            speech_buffer.append(frame_event.frame)
            vad_stream.push_frame(frame_event.frame)

        vad_task.cancel()

    # ================= SIP CALL ================= #

    if phone_number:
        try:
            sip_identity = f"sip_{phone_number}"

            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=config.SIP_TRUNK_ID,
                    sip_call_to=phone_number,
                    participant_identity=sip_identity,
                    wait_until_answered=True,
                )
            )

            await say(config.INITIAL_GREETING)

            try:
                await asyncio.wait_for(done_event.wait(), timeout=45)
            except asyncio.TimeoutError:
                logger.info("Call timed out.")
                await hangup_call()

        except Exception as e:
            logger.error(f"Call Error: {e}")

    logger.info("Shutting down agent...")
    ctx.shutdown()


# ================= RUN WORKER ================= #

if __name__ == "__main__":
    from livekit.agents import cli

    cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-agent",
        )
    )
