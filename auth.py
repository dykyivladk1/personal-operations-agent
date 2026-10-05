import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
]


def authenticate():
    creds = None

    # Load existing token if available
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json",
            SCOPES,
        )

    # Token missing or invalid
    if not creds or not creds.valid:

        # Refresh existing token
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                print("Existing token cannot be refreshed.")
                print("Starting new authentication...")
                creds = None

        # Authenticate from scratch
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES,
            )

            creds = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
            )

        # Save new/refreshed token
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return creds


if __name__ == "__main__":
    creds = authenticate()

    print("\nAuthentication successful!")
    print("Valid:", creds.valid)
    print("Expired:", creds.expired)
    print("Refresh token:", bool(creds.refresh_token))

    print("\nGranted scopes:")

    for scope in creds.scopes or []:
        print(" -", scope)