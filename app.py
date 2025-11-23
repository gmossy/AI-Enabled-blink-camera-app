from flask import Flask, jsonify, request, session
import os
from dotenv import load_dotenv
import asyncio
from aiohttp import ClientSession
from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth, BlinkTwoFARequiredError
from functools import wraps

from flask_cors import CORS

app = Flask(__name__)
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}})

# Load environment variables
load_dotenv()

app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersecret')

# Configure session for CORS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Global blink instance storage
blink_instances = {}

# Store recent logs for display
recent_logs = []
MAX_LOGS = 50

def add_log(message):
    """Add a log message to recent_logs"""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    recent_logs.append(f"[{timestamp}] {message}")
    if len(recent_logs) > MAX_LOGS:
        recent_logs.pop(0)
    print(f"[{timestamp}] {message}")  # Also print to console

def async_route(f):
    """Decorator to run async functions in Flask routes"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

async def get_blink(username, password):
    """Get or create a Blink instance for the given credentials"""
    key = f"{username}:{password}"
    if key not in blink_instances:
        blink = Blink(session=ClientSession())
        auth = Auth({"username": username, "password": password}, no_prompt=True)
        blink.auth = auth
        await blink.start()
        blink_instances[key] = blink
    return blink_instances[key]

@app.route('/api/cameras', methods=['GET'])
@async_route
async def get_cameras_route():
    username = session.get('username')
    password = session.get('password')
    add_log(f'GET /api/cameras - username: {username}, password: {"***" if password else None}')
    if not username or not password:
        add_log('ERROR: Not logged in - no session data')
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        blink = await get_blink(username, password)
        # Refresh session for the new event loop
        new_session = ClientSession()
        blink.session = new_session
        blink.auth.session = new_session
        await blink.refresh()
        cameras = []
        for name, camera in blink.cameras.items():
            # Get battery info from multiple sources
            battery = camera.battery
            if battery is None or battery == '':
                # Try battery_state
                battery = getattr(camera, 'battery_state', None)
            if battery is None or battery == '':
                # Try attributes dict
                if hasattr(camera, 'attributes') and isinstance(camera.attributes, dict):
                    battery = camera.attributes.get('battery_state', None) or camera.attributes.get('battery', None)
            if battery is None or battery == '':
                # Try battery_voltage
                battery_voltage = getattr(camera, 'battery_voltage', None)
                if battery_voltage:
                    battery = f"{battery_voltage}V"
            if battery is None or battery == '':
                # Check if it's a wired camera
                if hasattr(camera, 'attributes') and isinstance(camera.attributes, dict):
                    if camera.attributes.get('type') in ['mini', 'doorbell']:
                        battery = 'Wired'
                    else:
                        battery = 'Unknown'
                else:
                    battery = 'Unknown'
            
            # Get temperature from multiple sources
            temperature = camera.temperature
            if temperature is None:
                # Try temperature_c and convert to F
                temp_c = getattr(camera, 'temperature_c', None)
                if temp_c is not None:
                    temperature = int(temp_c * 9/5 + 32)
            if temperature is None:
                # Try attributes dict
                if hasattr(camera, 'attributes') and isinstance(camera.attributes, dict):
                    temperature = camera.attributes.get('temperature', None)
                    if temperature is None:
                        temp_c = camera.attributes.get('temperature_c', None)
                        if temp_c is not None:
                            temperature = int(temp_c * 9/5 + 32)
            if temperature is None:
                temperature = 'N/A'
            
            add_log(f'Camera {name}: battery={battery}, temp={temperature}')
            
            # Debug: log camera attributes to find motion/notification fields
            if hasattr(camera, 'attributes') and isinstance(camera.attributes, dict):
                add_log(f'Camera {name} attributes keys: {list(camera.attributes.keys())}')
            
            # Get motion and notification status
            motion_enabled = getattr(camera, 'motion_enabled', None)
            add_log(f'Camera {name} motion_enabled property: {motion_enabled}')
            
            # Check attributes dict if property doesn't exist
            if motion_enabled is None and hasattr(camera, 'attributes') and isinstance(camera.attributes, dict):
                motion_enabled = camera.attributes.get('motion_detection', None)
                add_log(f'Camera {name} motion_detection from attributes: {motion_enabled}')
            if motion_enabled is None:
                motion_enabled = True  # Default to True if unknown
            
            # For notifications, check if snoozed
            notifications_snoozed = getattr(camera, 'notifications_snoozed', None)
            add_log(f'Camera {name} notifications_snoozed property: {notifications_snoozed}')
            
            if notifications_snoozed is None and hasattr(camera, 'attributes') and isinstance(camera.attributes, dict):
                notifications_snoozed = camera.attributes.get('notifications_snoozed', None)
                add_log(f'Camera {name} notifications_snoozed from attributes: {notifications_snoozed}')
            notifications_enabled = not notifications_snoozed if notifications_snoozed is not None else True
            
            add_log(f'Camera {name}: FINAL motion_enabled={motion_enabled}, notifications_enabled={notifications_enabled}')
            
            import datetime
            cameras.append({
                'name': name,
                'armed': getattr(camera, 'arm', False),
                'battery': battery,
                'temperature': temperature,
                'motion_detected': getattr(camera, 'motion_detected', False),
                'motion_enabled': motion_enabled,
                'notifications_enabled': notifications_enabled,
                'thumbnail': getattr(camera, 'thumbnail', None),
                'updated_at': datetime.datetime.now().strftime("%I:%M:%S %p")
            })
        return jsonify(cameras)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera/<camera_name>/arm', methods=['POST'])
@async_route
async def arm_camera(camera_name):
    username = session.get('username')
    password = session.get('password')
    if not username or not password:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        blink = await get_blink(username, password)
        # Refresh session for the new event loop
        new_session = ClientSession()
        blink.session = new_session
        blink.auth.session = new_session
        if camera_name in blink.cameras:
            await blink.cameras[camera_name].async_arm(True)
            return jsonify({'status': 'success'})
        return jsonify({'error': 'Camera not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera/<camera_name>/disarm', methods=['POST'])
@async_route
async def disarm_camera(camera_name):
    username = session.get('username')
    password = session.get('password')
    if not username or not password:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        blink = await get_blink(username, password)
        # Refresh session for the new event loop
        new_session = ClientSession()
        blink.session = new_session
        blink.auth.session = new_session
        if camera_name in blink.cameras:
            await blink.cameras[camera_name].async_arm(False)
            return jsonify({'status': 'success'})
        return jsonify({'error': 'Camera not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera/<camera_name>/snapshot', methods=['POST'])
@async_route
async def request_snapshot(camera_name):
    """Request a new snapshot from the camera"""
    username = session.get('username')
    password = session.get('password')
    if not username or not password:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        blink = await get_blink(username, password)
        # Refresh session for the new event loop
        new_session = ClientSession()
        blink.session = new_session
        blink.auth.session = new_session
        
        if camera_name in blink.cameras:
            camera = blink.cameras[camera_name]
            await camera.snap_picture()
            await blink.refresh()  # Refresh to get the new thumbnail
            return jsonify({'status': 'success', 'thumbnail': camera.thumbnail})
        return jsonify({'error': 'Camera not found'}), 404
    except Exception as e:
        add_log(f'Snapshot error: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera/<camera_name>/motion', methods=['POST'])
@async_route
async def toggle_motion_detection(camera_name):
    """Toggle motion detection on/off for a camera"""
    username = session.get('username')
    password = session.get('password')
    if not username or not password:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json() or {}
    enabled = data.get('enabled', True)
    
    try:
        blink = await get_blink(username, password)
        new_session = ClientSession()
        blink.session = new_session
        blink.auth.session = new_session
        
        if camera_name in blink.cameras:
            camera = blink.cameras[camera_name]
            # Use async_arm instead of deprecated set_motion_detect
            await camera.async_arm(enabled)
            add_log(f'Motion detection {"enabled" if enabled else "disabled"} for {camera_name}')
            return jsonify({'status': 'success', 'motion_enabled': enabled})
        return jsonify({'error': 'Camera not found'}), 404
    except Exception as e:
        add_log(f'Motion toggle error: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera/<camera_name>/notifications', methods=['POST'])
@async_route
async def toggle_notifications(camera_name):
    """Toggle notification snooze on/off for a camera"""
    username = session.get('username')
    password = session.get('password')
    if not username or not password:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json() or {}
    enabled = data.get('enabled', True)
    
    try:
        blink = await get_blink(username, password)
        new_session = ClientSession()
        blink.session = new_session
        blink.auth.session = new_session
        
        if camera_name in blink.cameras:
            camera = blink.cameras[camera_name]
            # Snooze notifications means disable them
            # If enabled=True, we want notifications ON, so snooze=False
            snooze = not enabled
            
            # Try to set notification snooze if the method exists
            if hasattr(camera, 'set_notification_snooze'):
                await camera.set_notification_snooze(snooze)
            elif hasattr(camera.sync, 'set_notification_snooze'):
                await camera.sync.set_notification_snooze(snooze)
            else:
                add_log(f'Warning: Notification snooze not supported for {camera_name}')
                return jsonify({'error': 'Notification control not supported for this camera'}), 400
            
            add_log(f'Notifications {"enabled" if enabled else "snoozed"} for {camera_name}')
            return jsonify({'status': 'success', 'notifications_enabled': enabled})
        return jsonify({'error': 'Camera not found'}), 404
    except Exception as e:
        add_log(f'Notification toggle error: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/camera/<camera_name>/thumbnail', methods=['GET'])
@async_route
async def get_thumbnail(camera_name):
    """Get the thumbnail image for a camera"""
    username = session.get('username')
    password = session.get('password')
    if not username or not password:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        blink = await get_blink(username, password)
        # Refresh session for the new event loop
        new_session = ClientSession()
        blink.session = new_session
        blink.auth.session = new_session
        
        if camera_name in blink.cameras:
            camera = blink.cameras[camera_name]
            # Get the thumbnail image
            response = await camera.get_media()
            if response:
                image_data = await response.read()
                from flask import Response
                return Response(image_data, mimetype='image/jpeg')
            return jsonify({'error': 'No thumbnail available'}), 404
        return jsonify({'error': 'Camera not found'}), 404
    except Exception as e:
        add_log(f'Thumbnail error: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/events', methods=['GET'])
@async_route
async def get_events():
    username = session.get('username')
    password = session.get('password')
    if not username or not password:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        blink = await get_blink(username, password)
        # Refresh session for the new event loop
        new_session = ClientSession()
        blink.session = new_session
        blink.auth.session = new_session
        await blink.refresh()
        
        # Get videos from the last 24 hours
        videos = await blink.get_videos_metadata(since=None, stop=3)
        
        events = []
        for video in videos:
            events.append({
                'camera': video.get('device_name', 'Unknown'),
                'timestamp': video.get('created_at', 'unknown'),
                'type': 'motion',
                'thumbnail': video.get('thumbnail', None),
                'video_url': video.get('media', None),
                'id': video.get('id', None)
            })
        
        return jsonify(events)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def update_env_file(key, value):
    """Update or add a key-value pair in the .env file"""
    env_path = '.env'
    lines = []
    key_found = False
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()
            
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            key_found = True
        else:
            new_lines.append(line)
            
    if not key_found:
        if new_lines and not new_lines[-1].endswith('\n'):
             new_lines.append('\n')
        new_lines.append(f"{key}={value}\n")
        
    with open(env_path, 'w') as f:
        f.writelines(new_lines)

@app.route('/api/config', methods=['GET'])
def get_config():
    """Check if credentials are configured"""
    username = os.getenv('BLINK_USERNAME')
    password = os.getenv('BLINK_PASSWORD')
    
    masked_username = None
    if username:
        # Simple masking
        parts = username.split('@')
        if len(parts) == 2:
            masked_username = f"{parts[0][:1]}***@{parts[1]}"
        else:
            masked_username = f"{username[:1]}***"
            
    return jsonify({
        'has_credentials': bool(username and password),
        'username': masked_username
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update Blink credentials in .env"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
        
    try:
        update_env_file('BLINK_USERNAME', username)
        update_env_file('BLINK_PASSWORD', password)
        
        # Reload environment variables
        os.environ['BLINK_USERNAME'] = username
        os.environ['BLINK_PASSWORD'] = password
        
        return jsonify({'status': 'success', 'message': 'Configuration updated'})
    except Exception as e:
        return jsonify({'error': f'Failed to update config: {str(e)}'}), 500

# Rate limiting globals
login_attempts = []
MAX_LOGIN_ATTEMPTS = 10 # Increased for testing
LOGIN_WINDOW = 300  # 5 minutes
LOCKOUT_DURATION = 300 # 5 minutes
lockout_until = 0

@app.route('/api/login', methods=['POST'])
@async_route
async def login():
    import logging
    import time
    import json
    
    global lockout_until, login_attempts
    
    current_time = time.time()
    
    # Check if locked out
    if current_time < lockout_until:
        wait_seconds = int(lockout_until - current_time)
        minutes = wait_seconds // 60
        seconds = wait_seconds % 60
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        return jsonify({'error': f'Too many login attempts. Please wait {time_str}.'}), 429

    # Clean up old attempts
    login_attempts = [t for t in login_attempts if current_time - t < LOGIN_WINDOW]
    
    if len(login_attempts) >= MAX_LOGIN_ATTEMPTS:
        lockout_until = current_time + LOCKOUT_DURATION
        wait_seconds = LOCKOUT_DURATION
        minutes = wait_seconds // 60
        seconds = wait_seconds % 60
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        return jsonify({'error': f'Too many login attempts. Please wait {time_str}.'}), 429

    # Record this attempt
    login_attempts.append(current_time)

    username = os.getenv('BLINK_USERNAME')
    password = os.getenv('BLINK_PASSWORD')
    
    if not username or not password:
        logging.error('Missing Blink credentials in environment variables')
        return jsonify({'error': 'Server misconfiguration: missing credentials'}), 500
    
    try:
        add_log("Login attempt started")
        
        # DEBUG: Perform raw login request to see what's happening
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "27.0ANDROID_28373244",
            "hardware_id": "Blinkpy",
        }
        data = {
            "username": username,
            "client_id": "android",
            "scope": "client",
            "grant_type": "password",
            "password": password,
        }
        
        add_log("Sending raw login request to Blink...")
        async with ClientSession() as session:
            async with session.post("https://api.oauth.blink.com/oauth/token", data=data, headers=headers) as response:
                status = response.status
                text = await response.text()
                add_log(f"Raw login response: Status={status}, Body={text}")
                
                if status == 412:
                    add_log("2FA REQUIRED detected from raw response")
                    # We can't easily proceed with blinkpy if we consumed the 2FA trigger here?
                    # Actually, triggering it here is fine, we just need to tell the frontend.
                    # But we need to initialize blink object for later.
                    
                    # Re-initialize blink object so we have it for verification
                    blink = Blink(session=ClientSession())
                    auth = Auth({"username": username, "password": password}, no_prompt=True)
                    blink.auth = auth
                    # We don't call start() because it might fail/swallow error.
                    # We just store it for the PIN verification step.
                    key = f"{username}:{password}"
                    blink_instances[key] = blink
                    return jsonify({'status': '2fa_required'})
                
                elif status == 200:
                    add_log("Login successful from raw response! Initializing blinkpy...")
                    # Login worked! Now we can initialize blinkpy
                    blink = Blink(session=ClientSession())
                    auth = Auth({"username": username, "password": password}, no_prompt=True)
                    blink.auth = auth
                    # We can inject the token if we parsed it, but let's just let blink.start() do it
                    # assuming it will work now that we know credentials are good.
                    # But if blink.start() was failing before, maybe we should use the token?
                    # Let's try blink.start() again, maybe it was a transient issue?
                    await blink.start()
                    add_log(f"blink.start() completed. Cameras found: {len(blink.cameras) if blink.cameras else 0}")
                    
                    if not blink.cameras:
                         # If still no cameras, maybe we need to use the token we got?
                         add_log("Still no cameras after blink.start(). This is weird.")
                         return jsonify({'error': 'Login succeeded but no cameras found'}), 500
                         
                    # Store the blink instance
                    key = f"{username}:{password}"
                    blink_instances[key] = blink
                    
                    session['username'] = username
                    session['password'] = password
                    return jsonify({'status': 'success', 'cameras': len(blink.cameras)})
                    
                else:
                    add_log(f"Login failed with status {status}")
                    return jsonify({'error': f'Login failed: {status} - {text}'}), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f'Login failed: {e}')
        return jsonify({'error': f'Login failed: {str(e)}'}), 401
        
        # Store the blink instance
        key = f"{username}:{password}"
        blink_instances[key] = blink
        
        session['username'] = username
        session['password'] = password
        add_log(f"Login successful! {len(blink.cameras)} cameras found")
        return jsonify({'status': 'success', 'cameras': len(blink.cameras)})
    except BlinkTwoFARequiredError:
        add_log("2FA required - waiting for PIN")
        # Store temp instance for verification
        key = f"{username}:{password}"
        blink_instances[key] = blink
        return jsonify({'status': '2fa_required'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f'Login failed: {e}')
        return jsonify({'error': f'Login failed: {str(e)}'}), 401

@app.route('/api/verify-pin', methods=['POST'])
@async_route
async def verify_pin():
    import logging
    data = request.get_json()
    pin = data.get('pin')
    username = os.getenv('BLINK_USERNAME')
    password = os.getenv('BLINK_PASSWORD')
    
    if not pin or not username or not password:
        return jsonify({'error': 'Missing PIN or credentials'}), 400
        
    key = f"{username}:{password}"
    if key not in blink_instances:
        return jsonify({'error': 'Session expired, please login again'}), 401
        
    try:
        blink = blink_instances[key]
        
        # Refresh session for the new event loop
        new_session = ClientSession()
        blink.session = new_session
        blink.auth.session = new_session
        
        # Send the PIN to Blink
        add_log(f'Sending 2FA code: {pin}')
        logging.info(f'Sending 2FA code: {pin}')
        result = await blink.send_2fa_code(pin)
        add_log(f'2FA send_2fa_code result: {result}')
        
        # After successful 2FA, we need to setup and refresh to get cameras
        add_log('Calling setup_post_verify...')
        await blink.setup_post_verify()
        add_log(f'After setup_post_verify: {len(blink.cameras) if blink.cameras else 0} cameras')
        
        # Refresh to ensure we have latest data
        add_log('Calling refresh...')
        await blink.refresh()
        add_log(f'After refresh: {len(blink.cameras) if blink.cameras else 0} cameras')
        
        # Check if cameras were found
        if not blink.cameras:
             add_log('ERROR: No cameras after 2FA verification and refresh')
             logging.error('No cameras after 2FA verification')
             return jsonify({'error': 'Verification succeeded but no cameras found'}), 401
        
        session['username'] = username
        session['password'] = password
        add_log(f'PIN verification successful! {len(blink.cameras)} cameras found')
        return jsonify({'status': 'success', 'cameras': len(blink.cameras)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f'PIN verification failed: {e}')
        return jsonify({'error': f'PIN verification failed: {str(e)}'}), 500


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Return recent logs for display"""
    return jsonify({'logs': recent_logs})

@app.route('/api/logout', methods=['POST'])
def logout():
    username = session.get('username')
    password = session.get('password')
    
    # Clean up the blink instance
    if username and password:
        key = f"{username}:{password}"
        if key in blink_instances:
            # Close the session
            asyncio.run(blink_instances[key].session.close())
            del blink_instances[key]
    
    session.pop('username', None)
    session.pop('password', None)
    return jsonify({'status': 'logged out'})

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5001)
