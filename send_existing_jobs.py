import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

def clean_text(text):
    """Aggressively clean text - remove ALL non-printable ASCII characters"""
    if not text:
        return ""
    # Convert to string
    text = str(text)
    # Replace common problematic characters
    text = text.replace('\xa0', '')  # non-breaking space
    text = text.replace('\u200b', '')  # zero-width space
    text = text.replace('\u2013', '-')  # en dash
    text = text.replace('\u2014', '-')  # em dash
    text = text.replace('\u2018', "'")  # left single quote
    text = text.replace('\u2019', "'")  # right single quote
    text = text.replace('\u201c', '"')  # left double quote
    text = text.replace('\u201d', '"')  # right double quote
    # Keep only printable ASCII (32-126)
    text = ''.join(char for char in text if 32 <= ord(char) <= 126)
    return text.strip()

def send_saved_jobs_email():
    """Send email with all jobs from the database"""
    
    # Load jobs from database
    jobs_file = "jobs_database.json"
    
    if not os.path.exists(jobs_file):
        print("No jobs database found!")
        return
    
    with open(jobs_file, 'r') as f:
        jobs_dict = json.load(f)
    
    if not jobs_dict:
        print("Database is empty!")
        return
    
    # Convert dict to list
    jobs = list(jobs_dict.values())
    
    print("Found " + str(len(jobs)) + " jobs in database")
    
    # Get email credentials
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')
    recipient_email = os.environ.get('RECIPIENT_EMAIL', sender_email)
    
    if not sender_email or not sender_password:
        print("Email credentials not found!")
        return
    
    # Create email - use only ASCII characters
    subject = "All Saved Investment Banking Jobs - Total: " + str(len(jobs))
    
    # Build email body with aggressively cleaned data
    body_parts = []
    body_parts.append("<html><body>")
    body_parts.append("<h2>All Investment Banking Jobs from Database</h2>")
    body_parts.append("<p>Here are all " + str(len(jobs)) + " jobs that were previously found:</p>")
    
    for idx, job in enumerate(jobs, 1):
        title = clean_text(job.get('title', 'Unknown'))
        company = clean_text(job.get('company', 'Unknown'))
        location = clean_text(job.get('location', 'Unknown'))
        url = clean_text(job.get('url', ''))
        date = clean_text(str(job.get('found_date', ''))[:19])
        
        # Skip if title is empty after cleaning (those masked jobs)
        if not title or title == "Unknown" or len(title) < 3:
            continue
        
        body_parts.append('<div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px;">')
        body_parts.append('<p><strong>Job #' + str(idx) + '</strong></p>')
        body_parts.append('<h3 style="color: #0073b1; margin: 0;">' + title + '</h3>')
        body_parts.append('<p style="margin: 5px 0;"><strong>Company:</strong> ' + company + '</p>')
        body_parts.append('<p style="margin: 5px 0;"><strong>Location:</strong> ' + location + '</p>')
        
        if url:
            body_parts.append('<p style="margin: 5px 0;"><a href="' + url + '" style="color: #0073b1;">View Job Posting</a></p>')
        
        if date:
            body_parts.append('<p style="margin: 5px 0; color: #666; font-size: 12px;">Found: ' + date + '</p>')
        
        body_parts.append('</div>')
    
    body_parts.append("</body></html>")
    
    # Join body parts and ensure it's clean ASCII
    body = "".join(body_parts)
    body = clean_text(body)
    
    # Create message - completely ASCII
    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email
    
    # Send email
    try:
        print("Sending email with jobs...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())
        print("SUCCESS! Email sent!")
        print("Check your inbox at: " + recipient_email)
    except Exception as e:
        print("Error: " + clean_text(str(e)))

if __name__ == "__main__":
    send_saved_jobs_email()
