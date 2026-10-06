import os
import base64

from datetime import datetime
from zoneinfo import ZoneInfo
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from langchain.tools import tool


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
]

TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"
DEFAULT_TIMEZONE = "Europe/Vienna"


def authenticate():
    """Authenticate with Google APIs and return valid OAuth credentials."""

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


def normalize_datetime(
    value: str,
    timezone: str = DEFAULT_TIMEZONE,
) -> str:
    """
    Convert an ISO 8601 datetime into an RFC 3339 datetime with timezone.

    Naive datetimes are interpreted in the supplied IANA timezone.

    Examples:
        2026-10-07T00:00:00
        -> 2026-10-07T00:00:00+02:00

        2026-12-07T00:00:00
        -> 2026-12-07T00:00:00+01:00

        2026-10-07T00:00:00Z
        -> 2026-10-07T00:00:00+00:00
    """

    if not isinstance(value, str) or not value.strip():
        raise ValueError("Datetime value must be a non-empty ISO 8601 string.")

    value = value.strip()

    # datetime.fromisoformat() accepts +00:00 reliably.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid datetime '{value}'. "
            "Expected ISO 8601, for example "
            "'2026-10-07T18:00:00'."
        ) from exc

    if dt.tzinfo is None:
        try:
            tz = ZoneInfo(timezone)
        except Exception as exc:
            raise ValueError(
                f"Invalid IANA timezone '{timezone}'."
            ) from exc

        dt = dt.replace(tzinfo=tz)

    return dt.isoformat()


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


@tool
def create_email_draft(
    to: str,
    subject: str,
    body: str,
) -> dict:
    """
    Create a Gmail draft without sending it.

    Use this tool when the user wants to prepare, compose, or draft an
    email but does not explicitly want to send it yet.

    Args:
        to: Recipient email address.
        subject: Subject line of the email.
        body: Plain-text body of the email.

    Returns:
        A dictionary containing the created Gmail draft ID and status.
    """

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
    """
    Extract the plain-text body from a Gmail API message payload.

    This is an internal helper function and is not exposed to the agent
    as a tool.

    Args:
        payload: Gmail API message payload.

    Returns:
        Decoded plain-text email body, or an empty string if no
        plain-text content is available.
    """

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
    """
    Retrieve and parse a single Gmail message by its message ID.

    This is an internal helper used by get_emails.

    Args:
        message_id: Gmail message ID.

    Returns:
        A dictionary containing the message metadata and body.
    """

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


@tool
def get_emails(
    query: str = "",
    max_results: int = 10,
) -> list[dict]:
    """
    Search and retrieve emails from the user's Gmail inbox.

    Use this tool when the user asks to find, search, read, inspect,
    summarize, or check emails. The query supports Gmail search syntax,
    such as sender, subject, date, unread status, and keywords.

    Examples of valid queries:
        "from:john@example.com"
        "subject:interview"
        "is:unread"
        "newer_than:7d"
        "from:recruiter@example.com newer_than:30d"

    Args:
        query: Gmail search query. Leave empty to retrieve recent emails.
        max_results: Maximum number of emails to retrieve.

    Returns:
        A list of dictionaries containing email IDs, sender, recipient,
        subject, date, body, snippet, and thread ID.
    """

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


@tool
def send_email(
    to: str,
    subject: str,
    body: str,
) -> dict:
    """
    Send an email immediately using the user's Gmail account.

    Use this tool only when the user explicitly asks to send an email.
    If the user only asks to write, compose, prepare, or draft an email,
    use create_email_draft instead.

    Args:
        to: Recipient email address.
        subject: Subject line of the email.
        body: Plain-text body of the email.

    Returns:
        A dictionary containing the sent message ID, thread ID,
        and delivery status.
    """

    message = EmailMessage()

    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    sent_message = gmail.users().messages().send(
        userId="me",
        body={
            "raw": encoded_message
        },
    ).execute()

    return {
        "message_id": sent_message["id"],
        "thread_id": sent_message.get("threadId"),
        "status": "sent",
    }


@tool
def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    location: str | None = None,
    description: str | None = None,
    attendees: list[str] | None = None,
    timezone: str = DEFAULT_TIMEZONE,
) -> dict:
    """
    Create an event in the user's primary Google Calendar.

    Use this tool when the user explicitly asks to create, schedule,
    add, or book an event, appointment, meeting, reminder, or other
    calendar entry.

    Datetimes without an explicit timezone offset are interpreted in
    the supplied IANA timezone. The default is Europe/Vienna.

    Args:
        summary: Event title.
        start_time: Event start as an ISO 8601 datetime string,
            for example "2026-10-07T18:00:00".
        end_time: Event end as an ISO 8601 datetime string,
            for example "2026-10-07T19:00:00".
        location: Optional physical or virtual event location.
        description: Optional event description or notes.
        attendees: Optional list of attendee email addresses.
        timezone: IANA timezone name. Defaults to Europe/Vienna.

    Returns:
        A dictionary containing the created event ID, title,
        start and end times, location, and Google Calendar link.
    """

    normalized_start = normalize_datetime(
        start_time,
        timezone,
    )
    normalized_end = normalize_datetime(
        end_time,
        timezone,
    )

    start_dt = datetime.fromisoformat(normalized_start)
    end_dt = datetime.fromisoformat(normalized_end)

    if end_dt <= start_dt:
        raise ValueError(
            "end_time must be later than start_time."
        )

    event = {
        "summary": summary,
        "start": {
            "dateTime": normalized_start,
            "timeZone": timezone,
        },
        "end": {
            "dateTime": normalized_end,
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


@tool
def get_events(
    max_results: int = 10,
    time_min: str | None = None,
    time_max: str | None = None,
) -> list[dict]:
    """
    Retrieve events from the user's primary Google Calendar.

    Use this tool when the user asks about their schedule, calendar,
    upcoming events, appointments, meetings, or availability.

    Datetimes without an explicit timezone offset are interpreted as
    Europe/Vienna time.

    Args:
        max_results: Maximum number of events to retrieve.
        time_min: Optional lower time boundary as an ISO 8601 datetime.
            For example "2026-10-07T00:00:00".
            If omitted, the current time is used.
        time_max: Optional upper time boundary as an ISO 8601 datetime.
            For example "2026-10-08T00:00:00".

    Returns:
        A list of dictionaries containing event IDs, titles,
        descriptions, locations, start and end times, attendees,
        and Google Calendar links.
    """

    if max_results < 1:
        raise ValueError("max_results must be at least 1.")

    if time_min is None:
        time_min = datetime.now(
            ZoneInfo(DEFAULT_TIMEZONE)
        ).isoformat()
    else:
        time_min = normalize_datetime(
            time_min,
            DEFAULT_TIMEZONE,
        )

    params = {
        "calendarId": "primary",
        "timeMin": time_min,
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
        "timeZone": DEFAULT_TIMEZONE,
    }

    if time_max is not None:
        time_max = normalize_datetime(
            time_max,
            DEFAULT_TIMEZONE,
        )

        min_dt = datetime.fromisoformat(time_min)
        max_dt = datetime.fromisoformat(time_max)

        if max_dt <= min_dt:
            raise ValueError(
                "time_max must be later than time_min."
            )

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