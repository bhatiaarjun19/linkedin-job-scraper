import json
import os
import smtplib
from email.mime.text import MIMEText
import re

def clean_text(text):
    """
    Aggressively clean text:
    - normalize unicode
    - remove non-printable characters
    - strip anything that could break ASCII/UTF-8 encoding
    """
    if not text:
        return ""

    text = str(text)

    # Common unicode troublemakers
    replacements = {
        '\xa0': ' ',   # non-breaking space
        '\u200b': '',  # zero-width space
        '\u2013': '-', # en dash
        '\u2014': '-', # em dash
        '\u2018': "'",
        '\u2019': "'",
        '\u201c': '"',
        '\u201d': '"'
    }

    for k, v in replacements.items():
        text = text.replace(k, v)

    # Keep only printable characters
    text = ''.join(c for c in text if c.isprintable())

    return text.strip()


def send_saved_jobs_email():
    jobs_file = "jobs_database.json"

    if not os.path.exists(jobs_file):
        print("No jobs database found!")
        return

    with open(jobs_file, "r", encoding="utf-8") as f:
        jobs_dict = json.load(f)

    if not jobs_dict:
        print("Database is empty!")
        return

    jobs = list(jobs_dict.values())
    print(f"Found {len(jobs)} jobs in database")

    # Email credentials
    sender_email = clean_text(os.environ.get("SENDER_EMAIL"))
    sender_password = os.environ.get("SENDER_PASSWORD")
    recipient_email = clean_text(
        os.environ.get("RECIPIENT_EMAIL", sender_email)
    )

    if not sender_email or not sender_password:
        print("Email credentials not found!")
        return

    subject = clean_text(
        f"All Saved Investment Banking Jobs - Total: {len(jobs)}"
    )

    # Build HTML body
    body_parts = []
    body_parts.append("<html><body>")
    body_parts.append("<h2>All Investment Banking Jobs from Database</h2>")
    body_parts.append(
        f"<p>Here are all {len(jobs)} jobs that were previously found:</p>"
    )

    for idx, job in enumerate(jobs, 1):
        title = clean_text(job.get("title", "Unknown"))
        company = clean_text(job.get("company", "Unknown"))
        location = clean_text(job.get("location", "Unknown"))
        url = clean_text(job.get("url", ""))
        date = clean_text(str(job.get("found_date", ""))[:19])

        # Skip masked or broken listings
        if not title or title == "Unknown" or len(title) < 3:
            continue

        body_parts.append(
            '<div style="border:1px solid #ddd;padding:15px;margin:10px 0;border-radius:5px;">'
        )
        body_parts.append(f"<p><strong>Job #{idx}</strong></p>")
        body_parts.append(
            f'<h3 style="color:#0073b1;margin:0;">{title}</h3>'
        )
        body_parts.append(
            f"<p><strong>Company:</strong> {company}</p>"
        )
        body_parts.append(
            f"<p><strong>Location:</strong> {location}</p>"
        )

        if url:
            body_parts.append(
                f'<p><a href="{url}" style="color:#0073b1;">View Job Posting</a></p>'
            )

        if date:
            body_parts.append(
                f'<p style="color:#666;font-size:12px;">Found: {date}</p>'
            )

        body_parts.append("</div>")

    body_parts.append("</body></html>")

    body = clean_text("".join(body_parts))

    # IMPORTANT: explicitly declare UTF-8
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    try:
        print("Sending email with jobs...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(
                sender_email,
                [recipient_email],
                msg.as_string()
            )
        print("SUCCESS! Email sent!")
        print(f"Check your inbox at: {recipient_email}")

    except Exception as e:
        print("Error sending email:")
        print(clean_text(str(e)))


if __name__ == "__main__":
    send_saved_jobs_email()
