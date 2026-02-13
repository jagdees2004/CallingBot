import asyncio
import os
import certifi
from dotenv import load_dotenv
from livekit import api

os.environ['SSL_CERT_FILE'] = certifi.where()
load_dotenv()

async def main():
    lkapi = api.LiveKitAPI()
    trunk_id = os.getenv("OUTBOUND_TRUNK_ID")
    address = os.getenv("VOBIZ_SIP_DOMAIN")
    username = os.getenv("VOBIZ_USERNAME")
    password = os.getenv("VOBIZ_PASSWORD")
    number = os.getenv("VOBIZ_OUTBOUND_NUMBER")

    if not trunk_id:
        print("❌ Error: OUTBOUND_TRUNK_ID missing in .env")
        return

    print(f"Updating Trunk: {trunk_id} -> {address}")

    try:
        await lkapi.sip.update_outbound_trunk_fields(
            trunk_id,
            address=address,
            auth_username=username,
            auth_password=password,
            numbers=[number] if number else [],
        )
        print("✅ SIP Trunk updated!")
    except Exception as e:
        print(f"❌ Failed: {e}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(main())