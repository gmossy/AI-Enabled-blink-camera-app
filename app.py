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
            cameras.append({
                'name': name,
                'armed': getattr(camera, 'arm', False),
                'battery': getattr(camera, 'battery', 'N/A'),
                'temperature': getattr(camera, 'temperature', 'N/A'),
                'motion_detected': getattr(camera, 'motion_detected', False),
                'thumbnail': getattr(camera, 'thumbnail', None)
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

@app.route('/api/login', methods=['POST'])
@async_route
async def login():
    import logging
    username = os.getenv('BLINK_USERNAME')
    password = os.getenv('BLINK_PASSWORD')
    
    if not username or not password:
        logging.error('Missing Blink credentials in environment variables')
        return jsonify({'error': 'Server misconfiguration: missing credentials'}), 500
    
    try:
        add_log("Login attempt started")
        blink = Blink(session=ClientSession())
        auth = Auth({"username": username, "password": password}, no_prompt=True)
        blink.auth = auth
        add_log("Calling blink.start()...")
        await blink.start()
        add_log(f"blink.start() completed. Cameras found: {len(blink.cameras) if blink.cameras else 0}")
        
        if not blink.cameras:
            add_log('WARNING: No cameras returned from Blink')
            logging.error('Login may have failed: No cameras returned from Blink')
            return jsonify({'error': 'Login may have failed: No cameras returned'}), 401
        
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
        res = await blink.send_2fa_code(pin)
        add_log(f'2FA result: {res}, cameras: {len(blink.cameras) if blink.cameras else 0}')
        logging.info(f'2FA result: {res}, cameras: {len(blink.cameras) if blink.cameras else 0}')
        
        # Check if cameras were found (send_2fa_code returns None on success)
        if not blink.cameras:
             add_log('ERROR: No cameras after 2FA verification')
             logging.error('No cameras after 2FA verification')
             return jsonify({'error': 'Verification succeeded but no cameras found'}), 401
              
        # Refresh to get cameras (start() already does setup, but we can ensure)
        # await blink.refresh() # start() calls setup_post_verify which sets up cameras
        
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
