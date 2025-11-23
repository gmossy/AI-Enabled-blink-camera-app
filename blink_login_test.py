import asyncio
from aiohttp import ClientSession
from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth
import sys
import requests
import json
import os
from pathlib import Path
import time
import uuid


from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("BLINK_USERNAME")
PASSWORD = os.getenv("BLINK_PASSWORD")

if not USERNAME or not PASSWORD:
    print("Error: BLINK_USERNAME and BLINK_PASSWORD must be set in .env file")
    sys.exit(1)

# Cache/token storage configuration
CACHE_DIR = Path.home() / ".blink_cache"
TOKEN_FILE = CACHE_DIR / "auth_token.json"
DEVICE_FILE = CACHE_DIR / "device_info.json"

def ensure_cache_dir():
    """Ensure cache directory exists"""
    CACHE_DIR.mkdir(exist_ok=True)
    print(f"Cache directory: {CACHE_DIR}")

def generate_device_id():
    """Generate a unique device ID in ELECTRON_XXXXX format"""
    device_id = f"ELECTRON_{uuid.uuid4().hex[:8].upper()}"
    return device_id

def save_device_info(device_id, device_name="Blink Python Client"):
    """Save device information to cache"""
    ensure_cache_dir()
    device_info = {
        "device_id": device_id,
        "device_name": device_name,
        "created_at": time.time(),
        "last_used": time.time()
    }
    with open(DEVICE_FILE, 'w') as f:
        json.dump(device_info, f, indent=2)
    print(f"Device info saved: {device_id}")

def load_device_info():
    """Load device information from cache"""
    if DEVICE_FILE.exists():
        with open(DEVICE_FILE, 'r') as f:
            device_info = json.load(f)
            device_info['last_used'] = time.time()
            # Update last_used timestamp
            with open(DEVICE_FILE, 'w') as f2:
                json.dump(device_info, f2, indent=2)
            print(f"Loaded existing device: {device_info['device_id']}")
            return device_info
    return None

def save_auth_token(token_data):
    """Save authentication token to cache"""
    ensure_cache_dir()
    token_info = {
        "token": token_data,
        "saved_at": time.time(),
        "expires_at": time.time() + (24 * 60 * 60)  # Assume 24 hour expiry
    }
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_info, f, indent=2)
    print("Authentication token saved to cache")

def load_auth_token():
    """Load authentication token from cache"""
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'r') as f:
            token_info = json.load(f)
            # Check if token is still valid (not expired)
            if time.time() < token_info.get('expires_at', 0):
                print("Loaded cached authentication token")
                return token_info['token']
            else:
                print("Cached token expired, will need fresh login")
                os.remove(TOKEN_FILE)
    return None

def prompt_sms_verification():
    """Prompt user for SMS verification code with retry logic"""
    max_attempts = 3
    for attempt in range(max_attempts):
        print(f"\n📱 SMS Verification Required (Attempt {attempt + 1}/{max_attempts})")
        print("Please check your phone for an SMS verification code from Blink.")
        print("Note: SMS may take a few minutes depending on your country.")
        
        # Give user option to wait or enter code
        while True:
            response = input("Enter SMS code (or 'wait' to check again, 'resend' to request new code): ").strip()
            
            if response.lower() == 'wait':
                print("Waiting 30 seconds for SMS...")
                time.sleep(30)
                continue
            elif response.lower() == 'resend':
                print("Please use your mobile app to request a new verification code.")
                continue
            elif response.isdigit() and len(response) >= 4:
                return response
            else:
                print("Please enter a valid SMS verification code (numbers only).")
                continue
    
    print("❌ Maximum SMS verification attempts exceeded.")
    return None

async def start():
    async with ClientSession() as session:
        try:
            # Step 1: Check for cached authentication token
            cached_token = load_auth_token()
            
            # Step 2: Handle device registration
            device_info = load_device_info()
            if not device_info:
                device_id = generate_device_id()
                save_device_info(device_id)
                device_info = load_device_info()
            
            print(f"🔐 Device ID: {device_info['device_id']}")
            print(f"👤 Attempting to login with username: {USERNAME}")
            
            # Step 3: Initialize Blink with enhanced auth
            blink = Blink(session=session)
            auth = Auth({"username": USERNAME, "password": PASSWORD}, no_prompt=True)
            
            # Try to use cached token if available
            if cached_token:
                print("🔄 Using cached authentication token...")
                auth.token = cached_token
                blink.auth = auth
            else:
                print("🔑 Starting fresh authentication...")
                blink.auth = auth
            
            await blink.start()
            print("✅ Initial authentication step completed")
            
            # Step 4: Check authentication status and handle SMS verification
            print(f"🔍 Auth token exists: {bool(getattr(blink.auth, 'token', None))}")
            
            # Handle SMS/2FA verification
            if blink.auth.check_key_required():
                print("\n📲 SMS/2FA verification required")
                sms_code = prompt_sms_verification()
                
                if sms_code:
                    print(f"🔐 Submitting SMS verification code: {sms_code}")
                    try:
                        await auth.send_auth_key(blink, sms_code)
                        await blink.start()  # Re-initialize after verification
                        print("✅ SMS verification successful")
                        
                        # Save the new token after successful verification
                        if hasattr(blink.auth, 'token') and blink.auth.token:
                            save_auth_token(blink.auth.token)
                            
                    except Exception as sms_error:
                        print(f"❌ SMS verification failed: {sms_error}")
                        return 1
                else:
                    print("❌ SMS verification cancelled or failed")
                    return 1
            else:
                # Save token even if no SMS was required (for cached logins)
                if hasattr(blink.auth, 'token') and blink.auth.token:
                    save_auth_token(blink.auth.token)
            
            print(f"Number of cameras found: {len(blink.cameras) if blink.cameras else 0}")
            print(f"Camera data: {blink.cameras}")
            
            if not blink.cameras:
                print("Login may have failed: No cameras returned.")
                print("This could mean:")
                print("- Authentication failed")
                print("- No cameras are set up on this account")
                print("- API access is restricted")
                return 2
            
            print("Login successful! Cameras:")
            for cam_name, camera in blink.cameras.items():
                print(f"- {cam_name}: {camera}")
            return 0
            
        except requests.exceptions.ConnectionError as e:
            print(f"Network or DNS error: {e}")
            return 3
        except Exception as e:
            print(f"Login failed: {e}")
            return 1

if __name__ == "__main__":
    exit_code = asyncio.run(start())
    sys.exit(exit_code)
