"""
Test script to verify your email credentials work correctly.
Run this locally BEFORE deploying to GitHub Actions.

Usage:
    python test_email.py
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import getpass

def test_email():
    print("=" * 60)
    print("LinkedIn Job Scraper - Email Test")
    print("=" * 60)
    print("\nThis will test if your Gmail credentials work correctly.\n")
    
    # Get credentials from user
    sender_email = input("Enter your Gmail address: ").strip()
    print("\nEnter your Gmail App Password (16 characters, no spaces)")
    print("Not your regular password! See README for setup instructions.")
    sender_password = getpass.getpass("App Password: ").strip()
    
    recipient_email = input("\nWhere to send test email? (press Enter for same): ").strip()
    if not recipient_email:
        recipient_email = sender_email
    
    print("\n" + "=" * 60)
    print("Sending test email...")
    print("=" * 60)
    
    # Create test email
    subject = "✅ LinkedIn Job Scraper - Test Email"
    
    body = """
    <html>
    <body>
        <h2>🎉 Success! Your email configuration works!</h2>
        <p>This is a test email from your LinkedIn Job Scraper.</p>
        
        <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px;">
            <h3 style="color: #0073b1; margin: 0;">Sample Job Alert</h3>
            <p style="margin: 5px 0;"><strong>Company:</strong> Goldman Sachs</p>
            <p style="margin: 5px 0;"><strong>Location:</strong> New York, NY</p>
            <p style="margin: 5px 0;"><a href="https://linkedin.com" style="color: #0073b1;">View Job Posting</a></p>
        </div>
        
        <p>✅ <strong>Your email notifications are configured correctly!</strong></p>
        <p>You're ready to deploy to GitHub Actions.</p>
        
        <hr>
        <p style="color: #666; font-size: 12px;">
            Next steps:<br>
            1. Go to your GitHub repository<br>
            2. Add these credentials as GitHub Secrets<br>
            3. Enable GitHub Actions<br>
            4. You'll receive real job alerts every 15 minutes!
        </p>
    </body>
    </html>
    """
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email
    
    html_part = MIMEText(body, 'html')
    msg.attach(html_part)
    
    try:
        # Send email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            print("Connecting to Gmail SMTP server...")
            server.login(sender_email, sender_password)
            print("✅ Login successful!")
            
            server.send_message(msg)
            print("✅ Test email sent successfully!")
            
        print("\n" + "=" * 60)
        print("SUCCESS! ✨")
        print("=" * 60)
        print(f"\nCheck your inbox at: {recipient_email}")
        print("\nYour credentials work! Now add them to GitHub Secrets:")
        print(f"  SENDER_EMAIL: {sender_email}")
        print(f"  SENDER_PASSWORD: {sender_password}")
        print(f"  RECIPIENT_EMAIL: {recipient_email}")
        print("\nSee README.md for detailed GitHub setup instructions.")
        
    except smtplib.SMTPAuthenticationError:
        print("\n❌ ERROR: Authentication failed!")
        print("\nPossible issues:")
        print("1. You're using your regular Gmail password (you need an App Password)")
        print("2. App Password is incorrect")
        print("3. 2-Step Verification is not enabled on your Google account")
        print("\n📖 See README.md Step 1 for App Password setup instructions")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nPlease check:")
        print("1. Your internet connection")
        print("2. Email address is correct")
        print("3. App Password is correct (16 characters, no spaces)")

if __name__ == "__main__":
    test_email()
