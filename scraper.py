import requests
from bs4 import BeautifulSoup
import json
import os
import re
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
            # Product Marketing
            'product marketing manager',
            'associate product marketing manager',
            'product marketing associate',
            'product marketing specialist',
            'product marketing lead',
            'B2B product marketing manager',
            'SaaS product marketing manager',
            'launch marketing manager',
            'product launch manager',
            # Brand
            'brand manager',
            'associate brand manager',
            'brand marketing manager',
            'brand associate',
            'brand strategist',
            'brand strategy manager',
            'brand and integrated marketing manager',
            'corporate brand manager',
            'B2B brand manager',
            'commercial marketing manager',
            # Integrated & Campaign Marketing
            'integrated marketing manager',
            'marketing manager',
            'marketing associate',
            'marketing communications manager',
            'campaign marketing manager',
            'campaign manager marketing',
            'digital marketing manager',
            'field marketing manager',
            'segment marketing manager',
            # Strategy & GTM
            'product strategy manager',
            'product strategist',
            'GTM manager',
            'go to market manager',
            'go to market associate',
            'go to market strategy manager',
            'marketing strategy manager',
            'growth marketing manager',
            'demand generation manager',
            'market development manager',
        ]

        # Titles too senior for MBA + 2-3 yrs exp
        self.senior_title_keywords = [
            'senior director', 'sr. director', 'sr director',
            'vice president', 'vp ', ' vp,', '(vp)', 'svp', 'evp',
            'head of', 'chief ', 'cmo', 'ceo', 'coo',
            'principal ', 'group director', 'global director',
            'director of', 'director,',
        ]

        # Resume-based skill signals for relevance scoring (Prachita Purohit)
        # Each entry: (label shown in email, [keywords to match in JD], max points)
        self.resume_signals = [
            ('Brand Strategy / Management',
             ['brand management', 'brand strategy', 'brand stewardship', 'brand positioning',
              'brand equity', 'brand identity', 'brand manager', 'brand marketing',
              'brand building', 'brand communications'],
             2),
            ('Go-To-Market / Product Launch',
             ['go-to-market', 'go to market', 'gtm', 'product launch', 'market entry',
              'commercialization', 'launch strategy', 'product positioning', 'market introduction'],
             2),
            ('Consumer Insights / Market Research',
             ['consumer insights', 'consumer research', 'market research', 'customer research',
              'consumer behavior', 'customer insights', 'voice of customer', 'voc',
              'segmentation research', 'qualitative research', 'quantitative research'],
             1),
            ('Marketing Analytics / ROI',
             ['marketing analytics', 'marketing roi', 'data-driven', 'performance tracking',
              'kpi', 'metrics', 'tableau', 'sql', 'marketing measurement',
              'campaign analytics', 'reporting', 'marketing effectiveness'],
             1),
            ('B2B Marketing',
             ['b2b', 'business-to-business', 'enterprise marketing', 'b2b marketing',
              'account-based', 'abm', 'sales enablement', 'b2b saas'],
             1),
            ('Integrated / Campaign Marketing',
             ['integrated marketing', 'campaign', 'multi-channel', 'omnichannel',
              'cross-channel', 'paid media', 'email marketing', 'content marketing',
              'digital marketing', 'social media'],
             1),
            ('Pricing / Segmentation / Competitive',
             ['pricing strategy', 'price', 'customer segmentation', 'segmentation',
              'competitive analysis', 'competitive intelligence', 'benchmarking',
              'competitive landscape', 'market analysis'],
             1),
            ('Cross-functional Collaboration',
             ['cross-functional', 'cross functional', 'stakeholder', 'product management',
              'collaborate', 'partnership', 'sales team', 'channel management'],
             1),
        ]
        # Bonus: MBA preferred/required adds +1 (max total = 10)

        # No location filter — search all of United States
        self.max_years_experience = 4

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
        title_lower = title.lower()
        return any(kw in title_lower for kw in self.senior_title_keywords)

    # ── Resume-based relevance scoring ───────────────────────────────

    def score_job_by_resume(self, job, description):
        """
        Score a job out of 10 by matching the JD against Prachita's resume skills.
        Stores matched skill labels and score on the job dict.
        """
        text = description.lower()
        score = 0
        matched = []

        for label, keywords, max_pts in self.resume_signals:
            hits = sum(1 for kw in keywords if kw in text)
            if hits >= 2:
                score += max_pts
                matched.append(label)
            elif hits == 1:
                score += max(1, max_pts - 1)
                matched.append(label)

        # Bonus point if MBA is explicitly preferred or required
        if 'mba' in text:
            score += 1
            if 'MBA preferred' not in matched:
                matched.append('MBA preferred/required')

        score = min(score, 10)

        if score >= 8:
            match_label = 'Excellent Match'
            label_color, label_bg = '#137333', '#e6f4ea'
        elif score >= 5:
            match_label = 'Strong Match'
            label_color, label_bg = '#1a73e8', '#e8f0fe'
        elif score >= 3:
            match_label = 'Good Match'
            label_color, label_bg = '#e37400', '#fef7e0'
        else:
            match_label = 'Partial Match'
            label_color, label_bg = '#5f6368', '#f1f3f4'

        job['relevance_score'] = score
        job['match_label'] = match_label
        job['label_color'] = label_color
        job['label_bg'] = label_bg
        job['matched_skills'] = matched
        return score

    # ── Cold outreach template ────────────────────────────────────────

    def make_outreach_template(self, company, title):
        """Generate a 3-line LinkedIn DM template for a specific role."""
        company = self.clean_text(company)
        title = self.clean_text(title)
        return (
            "Hi [Name], I came across the " + title + " role at " + company +
            " and it really caught my eye — the intersection of brand/product marketing is exactly where I want to grow.|"
            "I'm an MBA with ~2 years of marketing experience and would love to hear your perspective on the team culture and what success looks like in this role.|"
            "Would you be open to a quick 15-minute chat? Completely no pressure — just looking to learn from someone doing great work at " + company + "."
        ).split('|')

    def make_referral_link(self, company, role_area):
        query = urllib.parse.quote(role_area + " " + company)
        return "https://www.linkedin.com/search/results/people/?keywords=" + query + "&origin=GLOBAL_SEARCH_HEADER"

    # ── Job description scraping ──────────────────────────────────────

    def scrape_job_description(self, url):
        try:
            time.sleep(random.uniform(2, 4))
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            desc = (
                soup.find('div', class_='show-more-less-html__markup') or
                soup.find('div', class_='description__text') or
                soup.find('section', class_='description')
            )
            return desc.get_text(separator=' ', strip=True) if desc else ""
        except Exception:
            return ""

    def extract_min_years(self, description):
        text = description.lower()
        patterns = [
            r'(\d+)\s*(?:-|to)\s*\d+\s*\+?\s*years?\s*(?:of\s+)?(?:relevant\s+|related\s+)?(?:work\s+)?experience',
            r'(\d+)\s*\+\s*years?\s*(?:of\s+)?(?:relevant\s+|related\s+)?(?:work\s+)?experience',
            r'(?:minimum|at least|min\.?)\s*(?:of\s+)?(\d+)\s*\+?\s*years?',
            r'(\d+)\s*years?\s*(?:of\s+)?(?:relevant\s+|related\s+)?(?:work\s+)?experience',
            r'experience\s+of\s+(\d+)\s*\+?\s*years?',
        ]
        years_found = []
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                try:
                    years_found.append(int(match.group(1)))
                except (IndexError, ValueError):
                    continue
        return min(years_found) if years_found else None

    def extract_salary(self, description):
        """Extract salary range from JD if listed."""
        match = re.search(r'\$[\d,]+\s*(?:k|K)?\s*(?:-|to)\s*\$[\d,]+\s*(?:k|K)?', description)
        return match.group(0) if match else None

    def extract_key_skills(self, description):
        lines = [l.strip() for l in description.split('\n') if l.strip()]
        qual_keywords = ['qualifications', 'requirements', 'what you', 'you bring', 'you have', 'about you']
        start = 0
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in qual_keywords):
                start = i + 1
                break
        snippets = []
        for line in lines[start:start + 15]:
            if 10 < len(line) < 200 and not any(
                skip in line.lower() for skip in ['equal opportunity', 'we are an', 'salary', 'compensation']
            ):
                snippets.append(line.lstrip('•-– ').strip())
            if len(snippets) == 6:
                break
        return snippets

    def enrich_with_jd(self, jobs):
        """Fetch JD for each job, filter 5+ year roles, extract skills & salary."""
        enriched = []
        total = len(jobs)
        for idx, job in enumerate(jobs, 1):
            print("  JD [" + str(idx) + "/" + str(total) + "] " + job['title'] + " @ " + job['company'])
            description = self.scrape_job_description(job['url'])
            min_years = self.extract_min_years(description)

            if min_years is not None and min_years > self.max_years_experience:
                print("    Filtered — requires " + str(min_years) + "+ yrs")
                continue

            job['years_required'] = str(min_years) + "+ years" if min_years else "Not specified"
            job['key_skills'] = self.extract_key_skills(description)
            job['salary'] = self.extract_salary(description)
            self.score_job_by_resume(job, description)
            enriched.append(job)
            print("    Kept — " + job['match_label'] + " (" + str(job['relevance_score']) + "/10) | " + job['years_required'])

        print("JD filter: kept " + str(len(enriched)) + " of " + str(total))
        return enriched

    # ── Search ────────────────────────────────────────────────────────

    def scrape_jobs_for_keyword(self, keyword):
        params = {
            'keywords': keyword,
            'location': 'United States',
            'f_TPR': 'r86400',
            'f_E': '3,4',
            'position': 1,
            'pageNum': 0
        }
        try:
            time.sleep(random.uniform(3, 6))
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []

            for card in soup.find_all('div', class_='base-card')[:12]:
                try:
                    job_id = card.get('data-entity-urn', '').split(':')[-1]
                    title_elem = card.find('h3', class_='base-search-card__title')
                    company_elem = card.find('h4', class_='base-search-card__subtitle')
                    location_elem = card.find('span', class_='job-search-card__location')
                    link_elem = card.find('a', class_='base-card__full-link')

                    if title_elem and company_elem and link_elem:
                        title = title_elem.text.strip()
                        location = location_elem.text.strip() if location_elem else 'United States'

                        if self.is_senior_role(title):
                            continue

                        jobs.append({
                            'id': job_id or link_elem.get('href', '').split('?')[0].split('/')[-1],
                            'title': title,
                            'company': company_elem.text.strip(),
                            'location': location,
                            'url': link_elem.get('href', '').split('?')[0],
                            'found_date': datetime.now().isoformat(),
                            'search_keyword': keyword
                        })
                except Exception:
                    continue
            return jobs
        except Exception:
            print("Error scraping " + keyword)
            return []

    def scrape_jobs(self):
        all_jobs = []
        print("Searching " + str(len(self.search_keywords)) + " keywords across all US locations...")

        for idx, keyword in enumerate(self.search_keywords, 1):
            print("  [" + str(idx) + "/" + str(len(self.search_keywords)) + "] " + keyword)
            jobs = self.scrape_jobs_for_keyword(keyword)
            print("      Found " + str(len(jobs)) + " jobs")
            all_jobs.extend(jobs)

        unique_jobs = {}
        for job in all_jobs:
            if job['id'] not in unique_jobs:
                unique_jobs[job['id']] = job

        print("Total unique jobs (pre-JD filter): " + str(len(unique_jobs)))
        return list(unique_jobs.values())

    def find_new_jobs(self, current_jobs, existing_jobs):
        return [job for job in current_jobs if job['id'] not in existing_jobs]

    # ── Email ─────────────────────────────────────────────────────────

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

        # Sort all jobs by relevance score (highest first)
        sorted_jobs = sorted(new_jobs, key=lambda j: j.get('relevance_score', 0), reverse=True)

        jobs_by_company = {}
        for job in sorted_jobs:
            jobs_by_company.setdefault(job.get('company', 'Other'), []).append(job)

        subject = "Job Alert: " + str(len(new_jobs)) + " New PMM / Brand / GTM Roles — Ranked by Resume Fit"

        excellent = [j for j in sorted_jobs if j.get('relevance_score', 0) >= 8]
        strong    = [j for j in sorted_jobs if 5 <= j.get('relevance_score', 0) < 8]
        other     = [j for j in sorted_jobs if j.get('relevance_score', 0) < 5]

        bp = []
        bp.append("""
<html><body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,sans-serif;">
<div style="max-width:680px;margin:24px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
""")

        # ── Header banner ─────────────────────────────────────────────
        bp.append("""
<div style="background:#0073b1;padding:24px 28px;">
  <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">PMM &amp; Brand Job Alert</h1>
  <p style="margin:6px 0 0;color:#cce4f6;font-size:13px;">
    """ + str(len(new_jobs)) + """ new role(s) found &bull; Ranked by how well they match your resume
  </p>
</div>
""")

        # ── Quick-scan summary table ──────────────────────────────────
        bp.append("""
<div style="padding:20px 28px 10px;">
  <h2 style="margin:0 0 12px;font-size:15px;color:#333;border-bottom:1px solid #e0e0e0;padding-bottom:8px;">
    At a Glance
  </h2>
  <table width="100%" cellpadding="6" cellspacing="0" style="font-size:12px;border-collapse:collapse;">
    <tr style="background:#f4f6f8;color:#555;">
      <th align="left" style="padding:6px 8px;border-bottom:1px solid #ddd;">#</th>
      <th align="left" style="padding:6px 8px;border-bottom:1px solid #ddd;">Role &amp; Company</th>
      <th align="left" style="padding:6px 8px;border-bottom:1px solid #ddd;">Location</th>
      <th align="left" style="padding:6px 8px;border-bottom:1px solid #ddd;">Exp.</th>
      <th align="center" style="padding:6px 8px;border-bottom:1px solid #ddd;">Match</th>
    </tr>
""")
        for i, job in enumerate(sorted_jobs, 1):
            score       = job.get('relevance_score', 0)
            match_label = job.get('match_label', '')
            lc          = job.get('label_color', '#5f6368')
            lb          = job.get('label_bg', '#f1f3f4')
            row_bg      = '#fff' if i % 2 == 0 else '#fafafa'
            bp.append(
                '<tr style="background:' + row_bg + ';">'
                '<td style="padding:6px 8px;color:#888;">' + str(i) + '</td>'
                '<td style="padding:6px 8px;">'
                  '<a href="' + str(job.get('url','')) + '" style="color:#0073b1;text-decoration:none;font-weight:600;">'
                  + self.clean_text(job.get('title','')) + '</a><br>'
                  '<span style="color:#666;">' + self.clean_text(job.get('company','')) + '</span>'
                '</td>'
                '<td style="padding:6px 8px;color:#555;">' + self.clean_text(job.get('location','')) + '</td>'
                '<td style="padding:6px 8px;color:#555;">' + self.clean_text(job.get('years_required','?')) + '</td>'
                '<td align="center" style="padding:6px 8px;">'
                  '<span style="background:' + lb + ';color:' + lc + ';font-size:11px;font-weight:700;'
                  'padding:2px 8px;border-radius:10px;white-space:nowrap;">'
                  + str(score) + '/10</span>'
                '</td>'
                '</tr>'
            )
        bp.append('</table></div>')

        # ── Section helper ────────────────────────────────────────────
        def section_header(label, color, bg):
            bp.append(
                '<div style="margin:20px 28px 0;padding:8px 12px;background:' + bg + ';'
                'border-left:4px solid ' + color + ';border-radius:0 4px 4px 0;">'
                '<span style="font-size:13px;font-weight:700;color:' + color + ';">' + label + '</span>'
                '</div>'
            )

        def job_card(job, idx):
            score       = job.get('relevance_score', 0)
            match_label = job.get('match_label', '')
            lc          = job.get('label_color', '#5f6368')
            lb          = job.get('label_bg', '#f1f3f4')
            matched     = job.get('matched_skills', [])
            skills      = job.get('key_skills', [])
            salary      = self.clean_text(job.get('salary', '')) or None

            # Left accent colour per match tier
            if score >= 8:
                accent = '#137333'
            elif score >= 5:
                accent = '#1a73e8'
            elif score >= 3:
                accent = '#e37400'
            else:
                accent = '#9e9e9e'

            bp.append(
                '<div style="margin:12px 28px;border:1px solid #e0e0e0;border-left:4px solid ' + accent + ';'
                'border-radius:0 6px 6px 0;background:#fff;padding:14px 16px;">'
            )

            # Row 1: title + badge
            bp.append(
                '<table width="100%" style="margin-bottom:4px;"><tr>'
                '<td style="vertical-align:top;">'
                  '<span style="font-size:14px;font-weight:700;color:#0073b1;">' + str(idx) + '. ' + self.clean_text(job.get('title','')) + '</span><br>'
                  '<span style="font-size:13px;color:#555;">' + self.clean_text(job.get('company','')) + ' &bull; ' + self.clean_text(job.get('location','')) + '</span>'
                '</td>'
                '<td align="right" style="vertical-align:top;white-space:nowrap;">'
                  '<span style="background:' + lb + ';color:' + lc + ';font-size:11px;font-weight:700;padding:3px 10px;border-radius:10px;">'
                  + match_label + ' &bull; ' + str(score) + '/10</span>'
                '</td>'
                '</tr></table>'
            )

            # Row 2: meta pills
            meta = []
            meta.append('<span style="background:#f1f3f4;color:#444;font-size:11px;padding:2px 8px;border-radius:10px;margin-right:6px;">'
                        '&#128197; Exp: ' + self.clean_text(job.get('years_required','Not specified')) + '</span>')
            if salary:
                meta.append('<span style="background:#f1f3f4;color:#444;font-size:11px;padding:2px 8px;border-radius:10px;margin-right:6px;">'
                            '&#128181; ' + salary + '</span>')
            bp.append('<p style="margin:6px 0;">' + ''.join(meta) + '</p>')

            # Row 3: matched skills as green chips
            if matched:
                bp.append('<p style="margin:8px 0 3px;font-size:12px;color:#555;font-weight:600;">Your skills this role needs:</p>')
                bp.append('<p style="margin:2px 0;">')
                for s in matched:
                    bp.append('<span style="display:inline-block;background:#e6f4ea;color:#137333;font-size:11px;'
                              'font-weight:600;padding:2px 8px;border-radius:10px;margin:2px 4px 2px 0;">'
                              '&#10003; ' + self.clean_text(s) + '</span>')
                bp.append('</p>')

            # Row 4: key JD requirements
            if skills:
                bp.append('<p style="margin:8px 0 3px;font-size:12px;color:#555;font-weight:600;">What they\'re looking for:</p>')
                bp.append('<ul style="margin:2px 0;padding-left:16px;font-size:12px;color:#444;line-height:1.6;">')
                for s in skills:
                    bp.append('<li>' + self.clean_text(s) + '</li>')
                bp.append('</ul>')

            # CTA
            bp.append(
                '<div style="margin-top:12px;">'
                '<a href="' + str(job.get('url','')) + '" style="display:inline-block;background:#0073b1;color:#fff;'
                'font-size:12px;font-weight:700;padding:7px 16px;border-radius:4px;text-decoration:none;">Apply Now &rarr;</a>'
                '<span style="font-size:11px;color:#aaa;margin-left:12px;">Found: ' + str(job.get('found_date',''))[:10] + '</span>'
                '</div>'
            )
            bp.append('</div>')

        # ── Excellent matches ─────────────────────────────────────────
        if excellent:
            section_header('Excellent Match — ' + str(len(excellent)) + ' role(s)', '#137333', '#e6f4ea')
            for i, job in enumerate(excellent, 1):
                job_card(job, i)

        # ── Strong matches ────────────────────────────────────────────
        if strong:
            offset = len(excellent)
            section_header('Strong Match — ' + str(len(strong)) + ' role(s)', '#1a73e8', '#e8f0fe')
            for i, job in enumerate(strong, offset + 1):
                job_card(job, i)

        # ── Other matches ─────────────────────────────────────────────
        if other:
            offset = len(excellent) + len(strong)
            section_header('Good / Partial Match — ' + str(len(other)) + ' role(s)', '#e37400', '#fef7e0')
            for i, job in enumerate(other, offset + 1):
                job_card(job, i)

        # ── Referrals & outreach ──────────────────────────────────────
        bp.append("""
<div style="margin:28px 28px 0;padding-bottom:4px;border-top:2px solid #0073b1;">
  <h2 style="margin:16px 0 4px;font-size:15px;color:#0073b1;">Referrals &amp; Outreach</h2>
  <p style="margin:0 0 12px;font-size:12px;color:#666;">
    For each company below: find someone to message on LinkedIn, then copy the DM template.
  </p>
</div>
""")
        referral_areas = ["product marketing", "brand marketing", "go to market"]

        for company, jobs in sorted(jobs_by_company.items()):
            company_clean = self.clean_text(company)
            top_job = max(jobs, key=lambda j: j.get('relevance_score', 0))
            template_lines = self.make_outreach_template(company_clean, top_job['title'])

            bp.append(
                '<div style="margin:10px 28px;border:1px solid #cce0f5;border-radius:6px;overflow:hidden;">'
                '<div style="background:#e8f0fe;padding:10px 14px;">'
                '<strong style="font-size:13px;color:#1a73e8;">' + company_clean + '</strong>'
                '</div>'
                '<div style="padding:12px 14px;background:#fff;">'
            )

            # Search links in a row
            bp.append('<p style="margin:0 0 6px;font-size:12px;color:#555;font-weight:600;">Find people to reach out to:</p>')
            bp.append('<p style="margin:0 0 10px;">')
            for area in referral_areas:
                link = self.make_referral_link(company_clean, area)
                bp.append('<a href="' + link + '" style="display:inline-block;font-size:11px;color:#0073b1;'
                          'border:1px solid #0073b1;padding:3px 10px;border-radius:10px;margin:2px 6px 2px 0;'
                          'text-decoration:none;">' + area.title() + ' &rarr;</a>')
            bp.append('</p>')

            # DM template
            bp.append('<p style="margin:0 0 4px;font-size:12px;color:#555;font-weight:600;">Copy-paste LinkedIn DM:</p>')
            bp.append('<div style="background:#f9f9f9;border:1px solid #e0e0e0;border-radius:4px;padding:10px 12px;">')
            for line in template_lines:
                bp.append('<p style="margin:4px 0;font-size:12px;color:#333;line-height:1.6;">' + self.clean_text(line) + '</p>')
            bp.append('</div>')
            bp.append('</div></div>')

        # ── Footer ────────────────────────────────────────────────────
        bp.append("""
<div style="padding:16px 28px;background:#f4f6f8;margin-top:24px;">
  <p style="margin:0;font-size:11px;color:#999;line-height:1.6;">
    Entry &amp; manager level only &bull; JD-verified (max 4 yrs experience) &bull; All US locations &bull;
    Scored against Prachita's resume &bull; Updated every 2 hrs, 7 AM–9 PM EST
  </p>
</div>
</div></body></html>
""")

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg.attach(MIMEText("".join(bp), 'html', 'utf-8'))

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
            print("EMAIL SENT SUCCESSFULLY - " + str(len(new_jobs)) + " jobs")
        except Exception as e:
            print("Error sending email: " + str(e))

    # ── Main ──────────────────────────────────────────────────────────

    def run(self):
        print("=" * 60)
        print("LinkedIn PMM / Brand / GTM Job Scraper")
        print("Entry/Manager Level | Preferred Cities | Ranked by Fit")
        print("=" * 60)

        existing_jobs = self.load_existing_jobs()
        print("Loaded " + str(len(existing_jobs)) + " existing jobs from database")

        current_jobs = self.scrape_jobs()
        print("\nSearch complete!")

        new_jobs = self.find_new_jobs(current_jobs, existing_jobs)
        print("Detected " + str(len(new_jobs)) + " new jobs — fetching JDs...")

        new_jobs = self.enrich_with_jd(new_jobs)

        for job in new_jobs:
            existing_jobs[job['id']] = job

        self.save_jobs(existing_jobs)
        print("Database updated with " + str(len(existing_jobs)) + " total jobs")

        if new_jobs:
            print("\nSending email...")
            self.send_email_notification(new_jobs)
            print("\nNew Jobs Summary (by score):")
            print("-" * 60)
            for job in sorted(new_jobs, key=lambda j: j.get('relevance_score', 0), reverse=True):
                print("  [" + str(job.get('relevance_score', 0)) + "/10 - " + job.get('match_label', '?') + "] " +
                      self.clean_text(job['title']) + " @ " +
                      self.clean_text(job['company']) + " | " +
                      job.get('years_required', '?'))
        else:
            print("\nNo new jobs after filtering. Database is up to date.")

        print("=" * 60)

if __name__ == "__main__":
    scraper = LinkedInJobScraper()
    scraper.run()
