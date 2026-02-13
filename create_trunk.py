import asyncio
import os
import certifi
from dotenv import load_dotenv
from livekit import api
from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo

os.environ['SSL_CERT_FILE'] = certifi.where()
load_dotenv()

async def main():
    lkapi = api.LiveKitAPI()
    
    sip_address = os.getenv("VOBIZ_SIP_DOMAIN")
    username = os.getenv("VOBIZ_USERNAME")
    password = os.getenv("VOBIZ_PASSWORD")
    number = os.getenv("VOBIZ_OUTBOUND_NUMBER")

    if not (sip_address and username and password):
        print("❌ Missing VOBIZ_* credentials in .env")
        return

    try:
        print(f"Creating trunk for {sip_address}...")
        trunk_info = SIPOutboundTrunkInfo(
            name="Vobiz Trunk",
            address=sip_address,
            auth_username=username,
            auth_password=password,
            numbers=[number] if number else [],
        )
        trunk = await lkapi.sip.create_outbound_trunk(CreateSIPOutboundTrunkRequest(trunk=trunk_info))
        print(f"✅ Trunk Created! ID: {trunk.sip_trunk_id}")
        print("👉 Add this ID to .env as VOBIZ_SIP_TRUNK_ID")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(main())