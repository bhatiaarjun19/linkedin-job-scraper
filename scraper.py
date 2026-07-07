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
import urllib.parse

class LinkedInJobScraper:
    def __init__(self):
        self.base_url = "https://www.linkedin.com/jobs/search/"
        self.jobs_file = "jobs_database.json"

        # Entry-level / early-career keywords (MBA + 2-3 yrs exp)
        self.search_keywords = [
            'associate product marketing manager',
            'product marketing manager',
            'product marketing associate',
            'associate brand manager',
            'brand manager',
            'brand marketing manager',
            'brand associate',
            'brand strategy manager',
            'brand strategist',
            'product strategy manager',
            'product strategist',
            'GTM manager',
            'go to market manager',
            'go to market associate',
            'marketing strategy manager',
        ]

        # Titles that indicate roles too senior for MBA + 2-3 yrs exp
        self.senior_title_keywords = [
            'senior director', 'sr. director', 'sr director',
            'vice president', 'vp ', ' vp,', '(vp)', 'svp', 'evp',
            'head of', 'chief ', 'cmo', 'ceo', 'coo',
            'principal ', 'group director', 'global director',
            'director of', 'director,',
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
        if os.path.exists(self.jobs_file):
            with open(self.jobs_file, 'r') as f:
                return json.load(f)
        return {}

    def save_jobs(self, jobs):
        with open(self.jobs_file, 'w') as f:
            json.dump(jobs, f, indent=2)

    def clean_text(self, text):
        if not text:
            return ""
        return str(text).encode('ascii', 'ignore').decode('ascii').strip()

    def is_senior_role(self, title):
        """Return True if the job title looks too senior for MBA + 2-3 yrs."""
        title_lower = title.lower()
        return any(kw in title_lower for kw in self.senior_title_keywords)

    def make_referral_link(self, company, role_area):
        """Build a LinkedIn people-search URL for potential referral contacts."""
        query = urllib.parse.quote(role_area + " " + company)
        return "https://www.linkedin.com/search/results/people/?keywords=" + query + "&origin=GLOBAL_SEARCH_HEADER"

    def scrape_jobs_for_keyword(self, keyword):
        """Scrape entry-level jobs for a specific keyword."""
        params = {
            'keywords': keyword,
            'location': 'United States',
            'f_TPR': 'r86400',   # posted in last 24 hours
            'f_E': '3,4',        # Associate (3) + Mid-Senior/Manager (4)
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

            for card in job_cards[:12]:
                try:
                    job_id = card.get('data-entity-urn', '').split(':')[-1]

                    title_elem = card.find('h3', class_='base-search-card__title')
                    company_elem = card.find('h4', class_='base-search-card__subtitle')
                    location_elem = card.find('span', class_='job-search-card__location')
                    link_elem = card.find('a', class_='base-card__full-link')

                    if title_elem and company_elem and link_elem:
                        title = title_elem.text.strip()

                        # Skip overly senior titles
                        if self.is_senior_role(title):
                            continue

                        job = {
                            'id': job_id or link_elem.get('href', '').split('?')[0].split('/')[-1],
                            'title': title,
                            'company': company_elem.text.strip(),
                            'location': location_elem.text.strip() if location_elem else 'United States',
                            'url': link_elem.get('href', '').split('?')[0],
                            'found_date': datetime.now().isoformat(),
                            'search_keyword': keyword
                        }
                        jobs.append(job)
                except Exception:
                    continue

            return jobs

        except Exception:
            print("Error scraping " + keyword)
            return []

    def scrape_jobs(self):
        all_jobs = []

        print("Searching " + str(len(self.search_keywords)) + " Product Marketing, Brand & GTM keywords (entry/manager level)...")

        for idx, keyword in enumerate(self.search_keywords, 1):
            print("  [" + str(idx) + "/" + str(len(self.search_keywords)) + "] " + keyword)
            jobs = self.scrape_jobs_for_keyword(keyword)
            print("      Found " + str(len(jobs)) + " jobs")
            all_jobs.extend(jobs)

        unique_jobs = {}
        for job in all_jobs:
            if job['id'] not in unique_jobs:
                unique_jobs[job['id']] = job

        print("Total unique jobs found: " + str(len(unique_jobs)))
        return list(unique_jobs.values())

    def find_new_jobs(self, current_jobs, existing_jobs):
        new_jobs = []
        for job in current_jobs:
            if job['id'] not in existing_jobs:
                new_jobs.append(job)
        return new_jobs

    def send_email_notification(self, new_jobs):
        if not new_jobs:
            print("No new jobs found")
            return

        sender_email = os.environ.get('SENDER_EMAIL')
        sender_password = os.environ.get('SENDER_PASSWORD')
        recipient_email = os.environ.get('RECIPIENT_EMAIL', sender_email)

        if not sender_email or not sender_password:
            print("Email credentials not found")
            return

        # Group jobs by company so referral section is easy to scan
        jobs_by_company = {}
        for job in new_jobs:
            company = job.get('company', 'Other')
            if company not in jobs_by_company:
                jobs_by_company[company] = []
            jobs_by_company[company].append(job)

        subject = "New Product Marketing, Brand & GTM Jobs - " + str(len(new_jobs)) + " Found"

        body_parts = []
        body_parts.append("<html><body style='font-family: Arial, sans-serif; max-width: 800px;'>")
        body_parts.append("<h2 style='color: #0073b1;'>New Product Marketing, Brand & GTM Opportunities</h2>")
        body_parts.append("<p>Found <strong>" + str(len(new_jobs)) + "</strong> new entry/manager-level job posting(s) in United States:</p>")

        # ── Job listings ──────────────────────────────────────────────
        body_parts.append("<h3 style='border-bottom: 2px solid #0073b1; padding-bottom: 5px;'>Job Postings</h3>")

        for company, jobs in sorted(jobs_by_company.items()):
            body_parts.append("<h4 style='color: #333; margin-top: 18px;'>" + self.clean_text(company) + "</h4>")
            for job in jobs:
                title = self.clean_text(job.get('title', ''))
                location = self.clean_text(job.get('location', ''))
                url = str(job.get('url', ''))
                keyword = self.clean_text(job.get('search_keyword', ''))
                date = str(job.get('found_date', ''))[:10]

                body_parts.append('<div style="border: 1px solid #ddd; padding: 12px 15px; margin: 8px 0; border-radius: 5px; background-color: #f9f9f9;">')
                body_parts.append('<p style="margin: 0 0 4px 0;"><strong style="color: #0073b1;">' + title + '</strong></p>')
                body_parts.append('<p style="margin: 3px 0; font-size: 13px;"><strong>Location:</strong> ' + location + '</p>')
                body_parts.append('<p style="margin: 3px 0; font-size: 13px;"><strong>Matched keyword:</strong> ' + keyword + '</p>')
                body_parts.append('<p style="margin: 3px 0;"><a href="' + url + '" style="color: #0073b1; font-weight: bold;">View Job Posting &rarr;</a></p>')
                body_parts.append('<p style="margin: 3px 0; color: #888; font-size: 11px;">Found: ' + date + '</p>')
                body_parts.append('</div>')

        # ── Referral contacts section ─────────────────────────────────
        body_parts.append("<hr style='margin: 30px 0;'>")
        body_parts.append("<h3 style='color: #0073b1; border-bottom: 2px solid #0073b1; padding-bottom: 5px;'>Reach Out for Referrals</h3>")
        body_parts.append("<p style='font-size: 13px; color: #555;'>Click a link below to search LinkedIn for people in similar roles at each company who may be able to refer you:</p>")

        referral_role_areas = ["product marketing", "brand marketing", "go to market"]

        for company in sorted(jobs_by_company.keys()):
            company_clean = self.clean_text(company)
            body_parts.append('<div style="border: 1px solid #cce0f5; padding: 12px 15px; margin: 8px 0; border-radius: 5px; background-color: #f0f7ff;">')
            body_parts.append('<p style="margin: 0 0 6px 0;"><strong>' + company_clean + '</strong></p>')
            for area in referral_role_areas:
                link = self.make_referral_link(company_clean, area)
                body_parts.append('<p style="margin: 3px 0; font-size: 13px;">')
                body_parts.append('<a href="' + link + '" style="color: #0073b1;">Search ' + area.title() + ' people at ' + company_clean + ' &rarr;</a>')
                body_parts.append('</p>')
            body_parts.append('</div>')

        body_parts.append("<hr style='margin-top: 30px;'>")
        body_parts.append("<p style='color: #666; font-size: 12px;'>Automated job alert - entry/manager level only (Associate + Mid-Senior). Updated every 2 hours between 7 AM - 10 PM EST.</p>")
        body_parts.append("</body></html>")
        body = "".join(body_parts)

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email

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
        print("=" * 60)
        print("LinkedIn Product Marketing, Brand & GTM Job Scraper")
        print("Entry/Manager Level - MBA + 2-3 yrs experience")
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
