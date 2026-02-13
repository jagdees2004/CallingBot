import asyncio
import os
import certifi
from dotenv import load_dotenv
from livekit import api
from livekit.protocol.sip import ListSIPOutboundTrunkRequest

os.environ['SSL_CERT_FILE'] = certifi.where()
load_dotenv()

async def main():
    lkapi = api.LiveKitAPI()
    try:
        print("Fetching Trunks...")
        res = await lkapi.sip.list_outbound_trunk(ListSIPOutboundTrunkRequest())
        for t in res.items:
            print(f"ID: {t.sip_trunk_id} | Name: {t.name} | Numbers: {t.numbers}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(main())