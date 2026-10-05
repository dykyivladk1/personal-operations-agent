import os
import base64

from datetime import datetime
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
]

TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"
DEFAULT_TIMEZONE = "Europe/Vienna"


def authenticate():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES,
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE,
                SCOPES,
            )

            creds = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
            )

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


creds = authenticate()

gmail = build(
    "gmail",
    "v1",
    credentials=creds,
)

calendar = build(
    "calendar",
    "v3",
    credentials=creds,
)


def create_email_draft(
    to: str,
    subject: str,
    body: str,
) -> dict:

    message = EmailMessage()

    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    draft = gmail.users().drafts().create(
        userId="me",
        body={
            "message": {
                "raw": encoded_message
            }
        },
    ).execute()

    return {
        "draft_id": draft["id"],
        "status": "created",
    }


def extract_email_body(payload: dict) -> str:

    body_data = payload.get(
        "body",
        {},
    ).get("data")

    if body_data:
        return base64.urlsafe_b64decode(
            body_data
        ).decode(
            "utf-8",
            errors="replace",
        )

    for part in payload.get("parts", []):

        if part.get("mimeType") == "text/plain":

            data = part.get(
                "body",
                {},
            ).get("data")

            if data:
                return base64.urlsafe_b64decode(
                    data
                ).decode(
                    "utf-8",
                    errors="replace",
                )

        if part.get("parts"):

            body = extract_email_body(part)

            if body:
                return body

    return ""


def get_email(message_id: str) -> dict:

    message = gmail.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()

    headers = message["payload"].get(
        "headers",
        [],
    )

    header_dict = {
        header["name"].lower(): header["value"]
        for header in headers
    }

    return {
        "id": message["id"],
        "thread_id": message["threadId"],
        "from": header_dict.get("from"),
        "to": header_dict.get("to"),
        "subject": header_dict.get("subject"),
        "date": header_dict.get("date"),
        "body": extract_email_body(
            message["payload"]
        ),
        "snippet": message.get("snippet"),
    }


def get_emails(
    query: str = "",
    max_results: int = 10,
) -> list[dict]:

    result = gmail.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results,
    ).execute()

    messages = result.get(
        "messages",
        [],
    )

    return [
        get_email(message["id"])
        for message in messages
    ]


def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    location: str | None = None,
    description: str | None = None,
    attendees: list[str] | None = None,
    timezone: str = DEFAULT_TIMEZONE,
) -> dict:

    event = {
        "summary": summary,
        "start": {
            "dateTime": start_time,
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_time,
            "timeZone": timezone,
        },
    }

    if location:
        event["location"] = location

    if description:
        event["description"] = description

    if attendees:
        event["attendees"] = [
            {"email": email}
            for email in attendees
        ]

    created_event = calendar.events().insert(
        calendarId="primary",
        body=event,
    ).execute()

    return {
        "id": created_event["id"],
        "summary": created_event.get("summary"),
        "start": created_event.get("start"),
        "end": created_event.get("end"),
        "location": created_event.get("location"),
        "html_link": created_event.get("htmlLink"),
    }


def get_events(
    max_results: int = 10,
    time_min: str | None = None,
    time_max: str | None = None,
) -> list[dict]:

    if time_min is None:
        time_min = datetime.now().astimezone().isoformat()

    params = {
        "calendarId": "primary",
        "timeMin": time_min,
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }

    if time_max:
        params["timeMax"] = time_max

    result = calendar.events().list(
        **params
    ).execute()

    events = result.get(
        "items",
        [],
    )

    return [
        {
            "id": event["id"],
            "summary": event.get("summary"),
            "description": event.get("description"),
            "location": event.get("location"),
            "start": event.get("start"),
            "end": event.get("end"),
            "attendees": event.get(
                "attendees",
                [],
            ),
            "html_link": event.get("htmlLink"),
        }
        for event in events
    ]