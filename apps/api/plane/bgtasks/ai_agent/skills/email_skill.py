import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

# Load local environment variables for testing
load_dotenv()

# Setup instructions:
# 1. Go to your Google Account -> Security -> 2-Step Verification
# 2. At the bottom, click "App passwords"
# 3. Create a new one named "Plane Agent" and copy the 16-character password.
GMAIL_USER = os.getenv("GMAIL_USER", "your-email@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "your-16-char-password")

def send_email(to_email: str, subject: str, body: str) -> bool:
    """Sends an email using Gmail SMTP."""
    print(f"📧 Attempting to send email to {to_email}...")
    
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        # Connect to Gmail SMTP server
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email successfully sent to {to_email}!")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

def check_unread_replies() -> list:
    """Reads the inbox for unread emails using Gmail IMAP."""
    print("📥 Checking inbox for unread replies...")
    replies = []
    
    try:
        # Connect to Gmail IMAP server
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select('inbox')

        # Search for unread emails
        status, messages = mail.search(None, 'UNSEEN')
        if status == 'OK':
            email_ids = messages[0].split()
            print(f"Found {len(email_ids)} unread emails.")
            
            for eid in email_ids:
                res, msg_data = mail.fetch(eid, '(RFC822)')
                if res == 'OK':
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    subject = msg['Subject']
                    sender = msg['From']
                    body = ""
                    
                    # Extract the body text
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = msg.get_payload(decode=True).decode()
                    
                    replies.append({"from": sender, "subject": subject, "body": body})
                    print(f"📩 Read email from {sender}: {subject}")
                    
        mail.logout()
        return replies
    except Exception as e:
        print(f"❌ Failed to check inbox: {e}")
        return []

if __name__ == "__main__":
    print("--- Testing Email Skill ---")
    print(f"Current User Configured: {GMAIL_USER}")
    
    # Uncomment and replace to test sending:
    # send_email("test-recipient@example.com", "Hello from Plane Agent", "<p>This is a test email from your AI.</p>")
    
    # Test reading inbox
    # check_unread_replies()
