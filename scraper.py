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
        # Comprehensive Investment Banking & M&A keywords
        self.search_keywords = [
            'investment banking',
            'investment banking analyst',
            'investment banking associate',
            'M&A',
            'mergers and acquisitions',
            'M&A analyst',
            'M&A associate',
            'capital markets',
            'leveraged finance',
            'financial advisory',
            'corporate development',
            'transaction advisory',
            'restructuring advisory',
            'ECM',  # Equity Capital Markets
            'DCM',  # Debt Capital Markets
        ]
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
    
    def clean_text(self, text):
        """Remove all non-ASCII characters from text"""
        if not text:
            return ""
        return str(text).encode('ascii', 'ignore').decode('ascii').strip()
    
    def scrape_jobs_for_keyword(self, keyword):
        """Scrape jobs for a specific keyword"""
        params = {
            'keywords': keyword,
            'location': 'United States',
            'f_TPR': 'r86400',
            'position': 1,
            'pageNum': 0
        }
        
        try:
            time.sleep(random.uniform(3, 6))
            
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            jobs = []
            job_cards = soup.find_all('div', class_='base-card')
            
            for card in job_cards[:12]:  # 12 jobs per keyword to manage volume
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
                            'found_date': datetime.now().isoformat(),
                            'search_keyword': keyword
                        }
                        jobs.append(job)
                except Exception as e:
                    continue
            
            return jobs
            
        except Exception as e:
            print("Error scraping " + keyword)
            return []
    
    def scrape_jobs(self):
        """Scrape jobs for all keywords"""
        all_jobs = []
        
        print("Searching " + str(len(self.search_keywords)) + " Investment Banking & M&A keywords...")
        
        for idx, keyword in enumerate(self.search_keywords, 1):
            print("  [" + str(idx) + "/" + str(len(self.search_keywords)) + "] " + keyword)
            jobs = self.scrape_jobs_for_keyword(keyword)
            print("      Found " + str(len(jobs)) + " jobs")
            all_jobs.extend(jobs)
        
        # Remove duplicates based on job ID
        unique_jobs = {}
        for job in all_jobs:
            if job['id'] not in unique_jobs:
                unique_jobs[job['id']] = job
        
        print("Total unique jobs found: " + str(len(unique_jobs)))
        return list(unique_jobs.values())
    
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
        
        sender_email = os.environ.get('SENDER_EMAIL')
        sender_password = os.environ.get('SENDER_PASSWORD')
        recipient_email = os.environ.get('RECIPIENT_EMAIL', sender_email)
        
        if not sender_email or not sender_password:
            print("Email credentials not found")
            return
        
        # Group jobs by search keyword
        jobs_by_keyword = {}
        for job in new_jobs:
            keyword = job.get('search_keyword', 'Other')
            if keyword not in jobs_by_keyword:
                jobs_by_keyword[keyword] = []
            jobs_by_keyword[keyword].append(job)
        
        # Simple subject with no emojis or special characters
        subject = "New Investment Banking & M&A Jobs - " + str(len(new_jobs)) + " Found"
        
        # Build email body with cleaned data
        body_parts = []
        body_parts.append("<html><body>")
        body_parts.append("<h2>New Investment Banking & M&A Opportunities</h2>")
        body_parts.append("<p>Found <strong>" + str(len(new_jobs)) + "</strong> new job posting(s) in United States:</p>")
        
        # Show jobs grouped by keyword
        for keyword, jobs in jobs_by_keyword.items():
            body_parts.append("<h3 style='color: #0073b1; margin-top: 20px; border-bottom: 2px solid #0073b1; padding-bottom: 5px;'>" + keyword.upper() + " (" + str(len(jobs)) + " jobs)</h3>")
            
            for job in jobs:
                title = self.clean_text(job.get('title', ''))
                company = self.clean_text(job.get('company', ''))
                location = self.clean_text(job.get('location', ''))
                url = str(job.get('url', ''))
                date = str(job.get('found_date', ''))[:19]
                
                body_parts.append('<div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; background-color: #f9f9f9;">')
                body_parts.append('<h4 style="color: #0073b1; margin: 0;">' + title + '</h4>')
                body_parts.append('<p style="margin: 5px 0;"><strong>Company:</strong> ' + company + '</p>')
                body_parts.append('<p style="margin: 5px 0;"><strong>Location:</strong> ' + location + '</p>')
                body_parts.append('<p style="margin: 5px 0;"><a href="' + url + '" style="color: #0073b1; font-weight: bold;">View Job Posting &rarr;</a></p>')
                body_parts.append('<p style="margin: 5px 0; color: #666; font-size: 12px;">Found: ' + date + '</p>')
                body_parts.append('</div>')
        
        body_parts.append("<hr style='margin-top: 30px;'>")
        body_parts.append("<p style='color: #666; font-size: 12px;'>This is an automated job alert. Jobs are updated every 30 minutes between 7 AM - 10 PM EST.</p>")
        body_parts.append("</body></html>")
        body = "".join(body_parts)
        
        # Create message with UTF-8 encoding
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email
        
        # Use UTF-8 encoding explicitly
        html_part = MIMEText(body, 'html', 'utf-8')
        msg.attach(html_part)
        
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
            print("EMAIL SENT SUCCESSFULLY - " + str(len(new_jobs)) + " jobs")
        except Exception as e:
            print("Error sending email: " + str(e))
    
    def run(self):
        """Main execution function"""
        print("=" * 60)
        print("LinkedIn Investment Banking & M&A Job Scraper")
        print("=" * 60)
        
        existing_jobs = self.load_existing_jobs()
        print("Loaded " + str(len(existing_jobs)) + " existing jobs from database")
        
        current_jobs = self.scrape_jobs()
        print("\nSearch complete!")
        print("Found " + str(len(current_jobs)) + " total unique jobs across all searches")
        
        new_jobs = self.find_new_jobs(current_jobs, existing_jobs)
        print("Detected " + str(len(new_jobs)) + " NEW jobs")
        
        for job in new_jobs:
            existing_jobs[job['id']] = job
        
        self.save_jobs(existing_jobs)
        print("Database updated with " + str(len(existing_jobs)) + " total jobs")
        
        if new_jobs:
            print("\nSending email notification...")
            self.send_email_notification(new_jobs)
            print("\nNew Jobs Summary:")
            print("-" * 60)
            for job in new_jobs:
                title = self.clean_text(job['title'])
                company = self.clean_text(job['company'])
                keyword = job.get('search_keyword', 'Unknown')
                print("  [" + keyword + "] " + title + " at " + company)
        else:
            print("\nNo new jobs found. Database is up to date.")
        
        print("=" * 60)

if __name__ == "__main__":
    scraper = LinkedInJobScraper()
    scraper.run()
