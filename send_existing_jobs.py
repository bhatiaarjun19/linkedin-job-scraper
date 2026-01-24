import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def clean_text(text):
    """Remove all non-ASCII characters from text"""
    if not text:
        return ""
    return str(text).encode('ascii', 'ignore').decode('ascii').strip()

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
    
    # Create email
    subject = "All Saved Investment Banking Jobs - " + str(len(jobs)) + " Total"
    
    # Build email body
    body_parts = []
    body_parts.append("<html><body>")
    body_parts.append("<h2>All Investment Banking Jobs from Database</h2>")
    body_parts.append("<p>Here are all " + str(len(jobs)) + " jobs that were previously found:</p>")
    
    for job in jobs:
        title = clean_text(job.get('title', 'Unknown'))
        company = clean_text(job.get('company', 'Unknown'))
        location = clean_text(job.get('location', 'Unknown'))
        url = str(job.get('url', ''))
        date = str(job.get('found_date', ''))[:19]
        
        body_parts.append('<div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px;">')
        body_parts.append('<h3 style="color: #0073b1; margin: 0;">' + title + '</h3>')
        body_parts.append('<p style="margin: 5px 0;"><strong>Company:</strong> ' + company + '</p>')
        body_parts.append('<p style="margin: 5px 0;"><strong>Location:</strong> ' + location + '</p>')
        body_parts.append('<p style="margin: 5px 0;"><a href="' + url + '" style="color: #0073b1;">View Job Posting</a></p>')
        body_parts.append('<p style="margin: 5px 0; color: #666; font-size: 12px;">Found: ' + date + '</p>')
        body_parts.append('</div>')
    
    body_parts.append("</body></html>")
    body = "".join(body_parts)
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email
    
    html_part = MIMEText(body, 'html', 'utf-8')
    msg.attach(html_part)
    
    # Send email
    try:
        print("Sending email with " + str(len(jobs)) + " jobs...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print("SUCCESS! Email sent with all " + str(len(jobs)) + " jobs!")
        print("Check your inbox at: " + recipient_email)
    except Exception as e:
        print("Error sending email: " + str(e))

if __name__ == "__main__":
    send_saved_jobs_email()
