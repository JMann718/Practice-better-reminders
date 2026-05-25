import os
import sys
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

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

def get_access_token():
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

def get_sessions_on_day(days_out, token):
    now = datetime.now(timezone.utc)
    target_date = (now + timedelta(days=days_out)).replace(hour=0, minute=0, second=0, microsecond=0)
    target_start = target_date.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    target_end = target_date.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    log(f"Looking for sessions between {target_start} and {target_end}")
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
    return response.json().get("items", [])

def get_incomplete_form_requests(record_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{PRACTICE_BETTER_BASE_URL}/consultant/formrequests",
        headers=headers,
        params={"records": record_id}
    )
    response.raise_for_status()
    forms = response.json().get("items", [])
    return [f for f in forms if not f.get("completed")]

def send_reminder_email(client_email, first_name, formatted_date):
    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = client_email
    msg["Subject"] = "Reminder: Please Complete Your Forms Before Your Appointment"
    body = (
        f"Hi {first_name},\n\n"
        f"This is a friendly reminder that your appointment is scheduled for {formatted_date}.\n\n"
        f"We noticed you have forms that still need to be completed. Please log into your Practice Better "
        f"account and look under Forms to see what is needed.\n\n"
        f"Forms not completed at least 48 hours prior to your scheduled appointment will cause the "
        f"appointment to be cancelled. It is important that I have this paperwork to prepare for our visit.\n\n"
        f"In addition, if you have Medicare, please ensure a referral from your physician is received by "
        f"my office as well prior to the appointment. Referral must include your diagnosis and recent labs. "
        f"Referrals should be faxed to 954-678-2590 or emailed to Jennifer@JMannNutrition.com\n\n"
        f"Thank you!"
    )
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, client_email, msg.as_string())
    log(f"Reminder sent to {first_name} ({client_email})")

def process_sessions(days_out, token):
    log(f"--- Checking sessions {days_out} days out ---")
    sessions = get_sessions_on_day(days_out, token)
    log(f"Found {len(sessions)} sessions")
    for session in sessions:
        client_record = session.get("clientRecord", {})
        record_id = client_record.get("id")
        profile = client_record.get("profile", {})
        first_name = profile.get("firstName", "there")
        client_name = f"{first_name} {profile.get('lastName', '')}".strip()
        client_email = profile.get("emailAddress")
        session_date = session.get("sessionDate", "")
        is_cancelled = session.get("cancelled", False)
        log(f"Checking client: {client_name}, email: {client_email}, date: {session_date}, cancelled: {is_cancelled}")
        if is_cancelled:
            log(f"Session for {client_name} is cancelled, skipping")
            continue
        if not client_email:
            log(f"No email for {client_name}, skipping")
            continue
        incomplete_forms = get_incomplete_form_requests(record_id, token)
        log(f"Incomplete forms for {client_name}: {len(incomplete_forms)}")
        if incomplete_forms:
            dt = datetime.strptime(session_date, "%Y-%m-%dT%H:%M:%SZ")
            dt_eastern = dt - timedelta(hours=4)
            formatted_date = dt_eastern.strftime("%m/%d/%Y at %I:%M %p")
            send_reminder_email(client_email, first_name, formatted_date)
        else:
            log(f"No incomplete forms for {client_name}, no email sent")

def main():
    log("Starting reminder script")
    token = get_access_token()
    log("Successfully got access token")
    process_sessions(7, token)
    process_sessions(4, token)

if __name__ == "__main__":
    main()
