import os
import requests
from datetime import datetime, timedelta
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
            "client_secret": PB_CLIENT_SECRET,
            "scope": "read"
        }
    )
    response.raise_for_status()
    return response.json()["access_token"]

# ============ FUNCTIONS ============
def get_appointments_in_7_days(token):
    """Fetch appointments scheduled 7 days from now."""
    target_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{PRACTICE_BETTER_BASE_URL}/v1/appointments",
        headers=headers,
        params={"date": target_date}
    )
    response.raise_for_status()
    return response.json().get("appointments", [])

def get_client_forms(client_id, token):
    """Check if client has incomplete forms."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{PRACTICE_BETTER_BASE_URL}/v1/clients/{client_id}/forms",
        headers=headers
    )
    response.raise_for_status()
    return response.json().get("forms", [])

def has_incomplete_forms(client_id, token):
    """Returns True if client has any incomplete forms."""
    forms = get_client_forms(client_id, token)
    return any(form.get("status") != "completed" for form in forms)

def send_reminder_email(client_email, client_name, appointment_date):
    """Send reminder email via Gmail."""
    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = client_email
    msg["Subject"] = "Reminder: Please Complete Your Forms Before Your Appointment"

    body = f"""
Hi {client_name},

This is a friendly reminder that your Initial Consultation is scheduled for {appointment_date}.

We noticed you have forms that still need to be completed. Please log into your client portal to complete them before your appointment.

Thank you!
    """
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, client_email, msg.as_string())

    print(f"Reminder sent to {client_name} ({client_email})")

def main():
    """Main function to check appointments and send reminders."""
    token = get_access_token()
    appointments = get_appointments_in_7_days(token)

    for appt in appointments:
        client_id = appt.get("client_id")
        client_email = appt.get("client_email")
        client_name = appt.get("client_name")
        appointment_date = appt.get("date")

        if has_incomplete_forms(client_id, token):
            send_reminder_email(client_email, client_name, appointment_date)

if __name__ == "__main__":
    main()
