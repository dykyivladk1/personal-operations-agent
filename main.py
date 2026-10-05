from utils.google_utils import get_emails

emails = get_emails(
    query="subject:interview newer_than:30d",
    max_results=10,
)
print(emails)