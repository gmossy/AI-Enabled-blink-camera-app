import os
import pytest
import asyncio
from aiohttp import ClientSession
from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

USERNAME = os.getenv("BLINK_USERNAME")
PASSWORD = os.getenv("BLINK_PASSWORD")

def test_blink_camera_access():
    """Test Blink camera API access with the new blinkpy 0.24.1 API"""
    
    if not USERNAME or not PASSWORD:
        pytest.skip("BLINK_USERNAME or BLINK_PASSWORD not set in environment")
    
    async def run_test():
        session = ClientSession()
        blink = Blink(session=session)
        auth = Auth({"username": USERNAME, "password": PASSWORD}, no_prompt=True)
        blink.auth = auth
        
        try:
            await blink.start()
            # Check if cameras are available
            assert blink.cameras, "No cameras returned from Blink API."
            print("Cameras found:")
            for cam_name, camera in blink.cameras.items():
                print(f"- {cam_name}: {camera}")
                print(f"  Attributes: {camera.attributes}")
            return True
        except Exception as e:
            pytest.fail(f"Login or API error: {e}")
            return False
        finally:
            await session.close()
    
    # Run the async test
    result = asyncio.run(run_test())
    assert result, "Test did not complete successfully"
