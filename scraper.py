import requests
from bs4 import BeautifulSoup
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import time
import random

class LinkedInJobScraper:
    def __init__(self):
        self.base_url = "https://www.linkedin.com/jobs/search/"
        self.jobs_file = "jobs_database.json"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
    def load_existing_jobs(self):
        """Load previously found jobs from JSON file"""
        if os.path.exists(self.jobs_file):
            with open(self.jobs_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_jobs(self, jobs):
        """Save jobs to JSON file"""
        with open(self.jobs_file, 'w') as f:
            json.dump(jobs, f, indent=2)
    
    def scrape_jobs(self):
        """Scrape investment banking jobs from LinkedIn"""
        params = {
            'keywords': 'investment banking',
            'location': 'United States',
            'f_TPR': 'r86400',  # Jobs posted in last 24 hours
            'position': 1,
            'pageNum': 0
        }
        
        try:
            # Add random delay to be respectful
            time.sleep(random.uniform(2, 5))
            
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            jobs = []
            job_cards = soup.find_all('div', class_='base-card')
            
            for card in job_cards[:20]:  # Limit to first 20 results
                try:
                    job_id = card.get('data-entity-urn', '').split(':')[-1]
                    
                    title_elem = card.find('h3', class_='base-search-card__title')
                    company_elem = card.find('h4', class_='base-search-card__subtitle')
                    location_elem = card.find('span', class_='job-search-card__location')
                    link_elem = card.find('a', class_='base-card__full-link')
                    
                    if title_elem and company_elem and link_elem:
                        job = {
                            'id': job_id or link_elem.get('href', '').split('?')[0].split('/')[-1],
                            'title': title_elem.text.strip(),
                            'company': company_elem.text.strip(),
                            'location': location_elem.text.strip() if location_elem else 'United States',
                            'url': link_elem.get('href', '').split('?')[0],
                            'found_date': datetime.now().isoformat()
                        }
                        jobs.append(job)
                except Exception as e:
                    print(f"Error parsing job card: {e}")
                    continue
            
            return jobs
            
        except Exception as e:
            print(f"Error scraping LinkedIn: {e}")
            return []
    
    def find_new_jobs(self, current_jobs, existing_jobs):
        """Compare current jobs with existing to find new ones"""
        new_jobs = []
        for job in current_jobs:
            if job['id'] not in existing_jobs:
                new_jobs.append(job)
        return new_jobs
    
    def send_email_notification(self, new_jobs):
        """Send email notification for new jobs"""
        if not new_jobs:
            print("No new jobs found")
            return
        
        # Get email credentials from environment variables
        sender_email = os.environ.get('SENDER_EMAIL')
        sender_password = os.environ.get('SENDER_PASSWORD')
        recipient_email = os.environ.get('RECIPIENT_EMAIL', sender_email)
        
        if not sender_email or not sender_password:
            print("Email credentials not found in environment variables")
            return
        
        # CRITICAL: Clean job data BEFORE using it in email body
        # This must happen before building the HTML string
        for job in new_jobs:
            job['title'] = str(job['title']).replace('\xa0', ' ').replace('\u200b', '').encode('ascii', 'ignore').decode('ascii')
            job['company'] = str(job['company']).replace('\xa0', ' ').replace('\u200b', '').encode('ascii', 'ignore').decode('ascii')
            job['location'] = str(job['location']).replace('\xa0', ' ').replace('\u200b', '').encode('ascii', 'ignore').decode('ascii')
        
        # Create email content - now all job data is clean
        subject = f"🚨 {len(new_jobs)} New Investment Banking Job(s) Found!"
        
        body = """
        <html>
        <body>
            <h2>New Investment Banking Jobs in United States</h2>
            <p>Found {} new job posting(s):</p>
        """.format(len(new_jobs))
        
        for job in new_jobs:
            body += """
            <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h3 style="color: #0073b1; margin: 0;">{}</h3>
                <p style="margin: 5px 0;"><strong>Company:</strong> {}</p>
                <p style="margin: 5px 0;"><strong>Location:</strong> {}</p>
                <p style="margin: 5px 0;"><a href="{}" style="color: #0073b1;">View Job Posting</a></p>
                <p style="margin: 5px 0; color: #666; font-size: 12px;">Found: {}</p>
            </div>
            """.format(job['title'], job['company'], job['location'], job['url'], job['found_date'][:19])
        
        body += """
        </body>
        </html>
        """
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email
        
        html_part = MIMEText(body, 'html')
        msg.attach(html_part)
        
        try:
            # Send email via Gmail SMTP
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
            print(f"✅ Email sent successfully with {len(new_jobs)} new jobs")
        except Exception as e:
            print(f"❌ Error sending email: {e}")
    
    def run(self):
        """Main execution function"""
        print(f"🔍 Starting LinkedIn job scraper at {datetime.now()}")
        
        # Load existing jobs
        existing_jobs = self.load_existing_jobs()
        print(f"📊 Loaded {len(existing_jobs)} existing jobs from database")
        
        # Scrape current jobs
        current_jobs = self.scrape_jobs()
        print(f"🌐 Found {len(current_jobs)} jobs in current search")
        
        # Find new jobs
        new_jobs = self.find_new_jobs(current_jobs, existing_jobs)
        print(f"✨ Detected {len(new_jobs)} new jobs")
        
        # Update database with new jobs
        for job in new_jobs:
            existing_jobs[job['id']] = job
        
        self.save_jobs(existing_jobs)
        
        # Send notification if new jobs found
        if new_jobs:
            self.send_email_notification(new_jobs)
            print("\n📋 New Jobs:")
            for job in new_jobs:
                # Clean the strings for console output
                title = str(job['title']).replace('\xa0', ' ').replace('\u200b', '').encode('ascii', 'ignore').decode('ascii')
                company = str(job['company']).replace('\xa0', ' ').replace('\u200b', '').encode('ascii', 'ignore').decode('ascii')
                print(f"  - {title} at {company}")
        else:
            print("✅ No new jobs found. Database is up to date.")

if __name__ == "__main__":
    scraper = LinkedInJobScraper()
    scraper.run()
