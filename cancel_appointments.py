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
JENNIFER_EMAIL = "Jennifer@jmannnutrition.com"
OFFICE_PHONE = "954-787-2554"

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

def get_sessions_in_48_hours(token):
    now = datetime.now(timezone.utc)
    target_date = (now + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
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

def cancel_session(session_id, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(
        f"{PRACTICE_BETTER_BASE_URL}/consultant/sessions/{session_id}/cancel",
        headers=headers,
        json={
            "notify": True,
            "notes": "Appointment cancelled due to incomplete intake forms."
        }
    )
    response.raise_for_status()
    log(f"Session {session_id} cancelled successfully")

def send_cancellation_email(client_email, first_name, formatted_date):
    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = client_email
    msg["Subject"] = "Appointment Cancelled - Please Call to Reschedule"
    body = (
        f"Hi {first_name},\n\n"
        f"Unfortunately your appointment scheduled for {formatted_date} has been cancelled "
        f"due to incomplete intake forms.\n\n"
        f"Please call our office at {OFFICE_PHONE} to reschedule your appointment.\n\n"
        f"If you have any questions, please don't hesitate to reach out.\n\n"
        f"Thank you!"
    )
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, client_email, msg.as_string())
    log(f"Cancellation email sent to {first_name} ({client_email})")

def send_alert_email(client_name, client_email, formatted_date):
    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = JENNIFER_EMAIL
    msg["Subject"] = f"Appointment Cancelled - Incomplete Forms: {client_name} - {formatted_date}"
    body = (
        "Hi Jennifer,\n\n"
        f"This is an automated alert: {client_name} ({client_email}) had an appointment on "
        f"{formatted_date} that has been cancelled due to incomplete intake forms.\n\n"
        f"The client has been notified to call the office at {OFFICE_PHONE} to reschedule.\n\n"
        "Thank you!"
    )
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, JENNIFER_EMAIL, msg.as_string())
    log(f"Alert email sent to Jennifer for {client_name}")

def main():
    log("Starting incomplete forms check")
    token = get_access_token()
    log("Successfully got access token")
    sessions = get_sessions_in_48_hours(token)
    log(f"Found {len(sessions)} sessions in 48-hour window")
    for session in sessions:
        client_record = session.get("clientRecord", {})
        record_id = client_record.get("id")
        session_id = session.get("id")
        profile = client_record.get("profile", {})
        first_name = profile.get("firstName", "there")
        client_name = f"{first_name} {profile.get('lastName', '')}".strip()
        client_email = profile.get("emailAddress")
        session_date = session.get("sessionDate", "")
        is_cancelled = session.get("cancelled", False)
        log(f"Checking client: {client_name}, date: {session_date}, cancelled: {is_cancelled}")
        if is_cancelled:
            log(f"Session {session_id} is already cancelled, skipping")
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
            cancel_session(session_id, token)
            send_cancellation_email(client_email, first_name, formatted_date)
            send_alert_email(client_name, client_email, formatted_date)
        else:
            log(f"No incomplete forms for {client_name}, no action needed")

if __name__ == "__main__":
    main()
