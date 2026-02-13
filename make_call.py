import os
import certifi
import argparse
import asyncio
import random
import json
from dotenv import load_dotenv
from livekit import api

# SSL Fix
os.environ['SSL_CERT_FILE'] = certifi.where()
load_dotenv()

async def main():
    parser = argparse.ArgumentParser(description="Make an outbound call.")
    parser.add_argument("--to", required=True, help="Phone number (e.g., +91...)")
    args = parser.parse_args()

    phone_number = args.to.strip()
    
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not (url and api_key and api_secret):
        print("❌ Error: Missing LiveKit credentials in .env")
        return

    lk_api = api.LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)
    room_name = f"call-{random.randint(10000, 99999)}"

    print(f"📞 Calling {phone_number} (Room: {room_name})")

    try:
        # Dispatch 'outbound-agent'
        dispatch_req = api.CreateAgentDispatchRequest(
            agent_name="outbound-agent",
            room=room_name,
            metadata=json.dumps({"phone_number": phone_number})
        )
        
        dispatch = await lk_api.agent_dispatch.create_dispatch(dispatch_req)
        print(f"✅ Dispatch sent! ID: {dispatch.id}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await lk_api.aclose()

if __name__ == "__main__":
    asyncio.run(main())