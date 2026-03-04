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

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{PRACTICE_BETTER_BASE_URL}/consultant/sessions",
        headers=headers,
        params={
            "date_gte": target_start,
            "date_lte": target_end,
            "limit": 100
        }
    )
    response.raise_for_status()
    return response.json().get("data", [])

def get_incomplete_form_requests(record_id, token):
    """Check if client has incomplete form requests."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{PRACTICE_BETTER_BASE_URL}/consultant/formrequests",
        headers=headers,
        params={"records": record_id}
    )
    response.raise_for_status()
    forms = response.json().get("data", [])
    return [f for f in forms if not f.get("completed")]

def send_reminder_email(client_email, client_name, session_date):
    """Send reminder email via Gmail."""
    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = client_email
    msg["Subject"] = "Reminder: Please Complete Your Forms Before Your Appointment"

    body = f"""
Hi {client_name},

This is a friendly reminder that your appointment is scheduled for {session_date}.

We noticed you have forms that still need to be completed. Please log into your client portal to complete them before your appointment.

Thank you!
    """
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, client_email, msg.as_string())

    print(f"Reminder sent to {client_name} ({client_email})")

def main():
    """Main function to check sessions and send reminders."""
    token = get_access_token()
    sessions = get_sessions_in_7_days(token)
    print(f"Found {len(sessions)} sessions in 7 days")

    for session in sessions:
        client_record = session.get("clientRecord", {})
        record_id = client_record.get("id")
        client_name = client_record.get("name", "Client")
        client_email = client_record.get("email")
        session_date = session.get("sessionDate", "")

        if not client_email:
            print(f"No email for client {client_name}, skipping")
            continue

        incomplete_forms = get_incomplete_form_requests(record_id, token)
        if incomplete_forms:
            send_reminder_email(client_email, client_name, session_date)

if __name__ == "__main__":
    main()
