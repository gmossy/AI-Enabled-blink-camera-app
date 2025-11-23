# Blink Camera Management System

A web application to manage Blink security cameras in your home.

## 🎉 Recent Updates (November 2025)

### Problem Solved: API Connectivity Issue ✅

**Issue**: The project was unable to connect to Blink API servers due to an outdated endpoint.
- ❌ Old: `blinkpy==0.14.0` using deprecated `prod.immedia-semi.com` (DNS failed)
- ✅ Fixed: Upgraded to `blinkpy==0.24.1` using correct `rest-prod.immedia-semi.com`

### Results

| Component | Status | Details |
|-----------|--------|---------|
| **API Endpoint** | ✅ Fixed | Now using `rest-prod.immedia-semi.com` with OAuth |
| **DNS Resolution** | ✅ Working | Resolves to `18.165.83.18` |
| **Backend Server** | ✅ Running | Flask API on port 5000 |
| **Frontend Server** | ✅ Running | React app on port 3000 |
| **blinkpy Version** | ✅ Updated | 0.14.0 → 0.24.1 (async/await API) |
| **Authentication** | ⚠️ 2FA Required | Blink requires two-factor authentication |

**See [UPGRADE_SUMMARY.md](UPGRADE_SUMMARY.md) for complete technical details.**

## Setup

### Prerequisites
- Python 3.11.9 (managed via pyenv)
- Node.js and npm
- Blink camera account

### 1. Install Python Dependencies

Create a virtual environment and install packages:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file with your Blink credentials:
```
BLINK_USERNAME=your_email@example.com
BLINK_PASSWORD=your_password
FLASK_SECRET_KEY=your_secret_key_here
```

**Note**: Blink requires two-factor authentication (2FA). You'll need to handle the PIN sent to your email during first login.

### 3. Install Frontend Dependencies

```bash
cd frontend
npm install
```

## Running the Application

### Start Backend Server
```bash
.venv/bin/python app.py
```
The Flask API will run on **http://127.0.0.1:5000**

### Start Frontend Development Server
```bash
cd frontend
npm start
```
The React app will run on **http://localhost:3000**

## Testing

Run the test suite:
```bash
.venv/bin/pytest test_blink_cameras.py -v
```

**Note**: Tests require valid Blink credentials in `.env` and may require 2FA PIN entry.

## Features
- 🎥 View live camera feeds
- 🔒 Arm/disarm cameras
- 🚨 View motion events
- 📹 Download recorded clips
- 🔐 Secure OAuth authentication with Blink servers

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/login` | POST | Authenticate with Blink |
| `/api/logout` | POST | Log out and clear session |
| `/api/cameras` | GET | List all cameras |
| `/api/camera/<name>/arm` | POST | Arm a specific camera |
| `/api/camera/<name>/disarm` | POST | Disarm a specific camera |
| `/api/events` | GET | Get motion events |

## Technology Stack

### Backend
- Flask 2.3.3 - Web framework
- blinkpy 0.24.1 - Blink camera API client (async)
- python-dotenv 1.0.0 - Environment management
- aiohttp - Async HTTP client

### Frontend
- React - UI framework
- Node.js/npm - Package management

## Troubleshooting

### DNS/Connection Issues
If you encounter connection errors, ensure you're using `blinkpy>=0.24.1`. Older versions use deprecated API endpoints.

### Two-Factor Authentication
Blink requires 2FA for security. When logging in for the first time:
1. A PIN will be sent to your email
2. You'll need to provide this PIN to complete authentication
3. Consider saving credentials after successful login for future sessions

### Python Version
This project requires Python 3.11.9. Use pyenv to manage Python versions:
```bash
pyenv install 3.11.9
pyenv local 3.11.9
```

## Contributing

This project uses:
- Python 3.11+ with async/await
- Type hints
- pytest for testing
- Black for code formatting

## License

MIT License
# AI-Enabled-blink-camera-app
