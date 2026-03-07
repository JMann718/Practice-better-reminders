import os
import requests
from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ============ CONFIGURATION (from GitHub Secrets) ============
PB_CLIENT_ID = os.environ["PB_CLIENT_ID"]
PB_CLIENT_SECRET = os.environ["PB_CLIENT_SECRET"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

PRACTICE_BETTER_BASE_URL = "https://api.practicebetter.io"

# ============ GET OAuth TOKEN ============
def get_access_token():
    """Get OAuth2 access token using client credentials."""
    response = requests.post(
        f"{PRACTICE_BETTER_BASE_URL}/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": PB_CLIENT_ID,
            "client_secret": PB_CLIENT_SECRET
        }
    )
    response.raise_for_status()
    return response.json()["access_token"]

# ============ FUNCTIONS ============
def get_sessions_in_7_days(token):
    """Fetch sessions scheduled 7 days from now."""
    now = datetime.now(timezone.utc)
    target_start = (now + timedelta(days=7)).replace(hour=0, minute=0, second=0).isoformat()
    target_end = (now + timedelta(days=7)).replace(hour=23, minute=59, second=59).isoformat()

    print(f"Looking for sessions between {target_start} and {target_end}")
