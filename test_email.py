"""Test Gmail SMTP connection directly (no Django needed)"""
import smtplib
from email.mime.text import MIMEText

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USER = 'marvelsafari@gmail.com'
EMAIL_PASSWORD = 'ijvewazypkbciysl'

msg = MIMEText('Your Marvel Safari email is working! This is a test.')
msg['Subject'] = 'Test from Marvel Safari'
msg['From'] = EMAIL_USER
msg['To'] = EMAIL_USER

print(f"Connecting to {EMAIL_HOST}:{EMAIL_PORT} via TLS...")
try:
    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        print("Connected! Logging in...")
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        print("Logged in! Sending email...")
        server.sendmail(EMAIL_USER, [EMAIL_USER], msg.as_string())
        print("SUCCESS: Email sent! Check your inbox at marvelsafari@gmail.com")
except smtplib.SMTPAuthenticationError as e:
    print(f"AUTHENTICATION FAILED: {e}")
    print("Your app password may be invalid. Generate a new one at:")
    print("https://myaccount.google.com/apppasswords")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
