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

        self.search_keywords = [
            # Product Marketing
            'product marketing manager', 'associate product marketing manager',
            'product marketing associate', 'product marketing specialist',
            'B2B product marketing manager', 'SaaS product marketing manager',
            'launch marketing manager', 'product launch manager',
            # Brand
            'brand manager', 'associate brand manager', 'brand marketing manager',
            'brand associate', 'brand strategist', 'brand strategy manager',
            'brand and integrated marketing manager', 'corporate brand manager',
            'B2B brand manager', 'commercial marketing manager',
            # Integrated & Campaign
            'integrated marketing manager', 'marketing manager', 'marketing associate',
            'marketing communications manager', 'campaign marketing manager',
            'digital marketing manager', 'field marketing manager', 'segment marketing manager',
            # GTM & Strategy
            'product strategy manager', 'product strategist', 'GTM manager',
            'go to market manager', 'go to market associate', 'go to market strategy manager',
            'marketing strategy manager', 'growth marketing manager',
            'demand generation manager', 'market development manager',
        ]

        self.senior_title_keywords = [
            'senior ', 'sr. ', 'sr ',          # catches "Sr PMM", "Senior Brand Manager"
            'senior director', 'sr. director', 'sr director',
            'vice president', 'vp ', ' vp,', '(vp)', 'svp', 'evp',
            'head of', 'chief ', 'cmo', 'ceo', 'coo',
            'principal ', 'group director', 'global director',
            'director of', 'director,', 'staff ',
        ]

        # Title must contain at least one of these to pass role-type filter
        self.required_title_terms = [
            'marketing', 'brand', 'gtm', 'go to market', 'go-to-market',
            'product strategy', 'growth marketing', 'demand generation', 'campaign',
            'communications', 'commercialization',
        ]

        # Drop roles whose titles contain these even if they passed the above check
        self.blocked_title_keywords = [
            'sales manager', 'sales operations', 'portfolio manager',
            'social media manager', 'social media community',
            'account manager', 'project manager', 'office manager',
            'operations manager', 'product operations',
            'influencer manager', 'talent marketing',
            'events manager', 'event manager',
        ]

        # ── Scoring signals (Prachita Purohit resume) ────────────────
        # Each: (display label, [JD phrases to match], max pts)
        self.resume_signals = [
            ('Brand Strategy & Management',
             ['brand management', 'brand strategy', 'brand positioning', 'brand stewardship',
              'brand equity', 'brand identity', 'brand marketing', 'brand building',
              'brand communications', 'brand development', 'brand guidelines', 'brand manager',
              'brand architecture', 'brand voice', 'brand awareness'],
             2),
            ('Go-To-Market & Product Launch',
             ['go-to-market', 'go to market', 'gtm strategy', 'product launch',
              'market entry', 'commercialization', 'launch strategy', 'product positioning',
              'launch plan', 'market penetration', 'launch execution', 'launch marketing',
              'product introduction', 'revenue launch', 'gtm execution'],
             2),
            ('Consumer & Market Research',
             ['consumer insights', 'consumer research', 'market research', 'customer insights',
              'consumer behavior', 'voice of customer', 'primary research',
              'qualitative research', 'quantitative research', 'customer research',
              'audience research', 'survey', 'focus group'],
             1),
            ('Marketing Analytics & Performance',
             ['marketing analytics', 'marketing roi', 'data-driven marketing',
              'performance marketing', 'marketing measurement', 'campaign performance',
              'marketing effectiveness', 'marketing metrics', 'analytics dashboard',
              'kpi tracking', 'a/b testing', 'attribution', 'reporting dashboard'],
             1),
            ('B2B / Enterprise Marketing',
             ['b2b marketing', 'business-to-business', 'enterprise marketing',
              'account-based marketing', 'abm', 'b2b saas', 'b2b brand',
              'b2b product marketing', 'b2b demand', 'commercial marketing'],
             1),
            ('Integrated & Campaign Marketing',
             ['integrated marketing', 'integrated campaign', 'multi-channel marketing',
              'omnichannel marketing', 'cross-channel', 'marketing campaigns',
              'campaign strategy', 'digital marketing strategy', 'content marketing strategy',
              'paid social', 'email campaign', 'marketing mix'],
             1),
            ('Pricing, Segmentation & Competitive',
             ['pricing strategy', 'price strategy', 'customer segmentation',
              'market segmentation', 'competitive analysis', 'competitive intelligence',
              'competitive landscape', 'competitive positioning', 'market analysis',
              'value proposition', 'pricing architecture', 'segment strategy'],
             1),
            ('Cross-functional & Stakeholder',
             ['cross-functional', 'cross functional', 'stakeholder management',
              'cross-team collaboration', 'channel management', 'go-to-market alignment',
              'sales and marketing alignment', 'product collaboration', 'sales enablement'],
             1),
            # Industry/context bonuses
            ('CPG / Consumer Goods',
             ['consumer goods', 'cpg', 'fmcg', 'consumer packaged goods',
              'retail marketing', 'shopper marketing', 'trade marketing'],
             1),
            ('Tech / SaaS / Startup',
             ['saas', 'software', 'startup', 'series a', 'series b', 'series c',
              'scale-up', 'early stage', 'growth stage', 'venture-backed', 'product-led'],
             1),
            ('Healthcare / Global Health',
             ['healthcare', 'health care', 'global health', 'pharma', 'biotech',
              'medical device', 'digital health', 'healthtech'],
             1),
        ]
        # Bonuses: +1 MBA in JD, +1 title match → max raw ~14, clamped to 10

        self.max_years_experience = 4

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    # ── Utilities ─────────────────────────────────────────────────────

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
        t = title.lower()
        if any(kw in t for kw in self.senior_title_keywords):
            return True
        if not any(term in t for term in self.required_title_terms):
            return True
        if any(kw in t for kw in self.blocked_title_keywords):
            return True
        return False

    # ── Relevance scoring ─────────────────────────────────────────────

    TITLE_MATCH_TERMS = [
        'brand manager', 'brand marketing', 'brand strategist', 'brand strategy',
        'product marketing', 'integrated marketing', 'go to market', 'gtm',
        'marketing associate', 'marketing manager', 'brand associate',
        'product launch', 'campaign manager',
    ]

    def score_job_by_resume(self, job, description):
        """
        Score 0-10 against Prachita's resume.
        11 skill/industry signals + MBA bonus + title-match bonus → clamped to 10.
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
                score += 1
                matched.append(label)

        if 'mba' in text:
            score += 1
            matched.append('MBA preferred/required')

        if any(t in job.get('title', '').lower() for t in self.TITLE_MATCH_TERMS):
            score += 1
            matched.append('Strong title alignment')

        score = min(score, 10)

        if score >= 8:
            label, color, bg = 'Excellent Match', '#137333', '#e6f4ea'
        elif score >= 6:
            label, color, bg = 'Strong Match',    '#1a73e8', '#e8f0fe'
        else:
            label, color, bg = 'Good Match',      '#e37400', '#fef7e0'

        job['relevance_score'] = score
        job['match_label']     = label
        job['label_color']     = color
        job['label_bg']        = bg
        job['matched_skills']  = matched
        return score

    # ── Outreach helpers ──────────────────────────────────────────────

    def people_search_links(self, company, title):
        """
        5 targeted LinkedIn people searches: same-role peers, direct hiring
        manager (role-aware title), broader marketing leadership, recruiter
        focused on marketing, and Babson alumni at the company.
        Quoted company + title for precision.
        """
        t = title.lower()
        def url(q):
            return ('https://www.linkedin.com/search/results/people/?keywords='
                    + urllib.parse.quote(q))

        co = '"' + company + '"'

        # Peer: exact same functional area
        if 'product marketing' in t:
            peer_q   = co + ' "product marketing manager"'
            mgr_q    = co + ' "director of product marketing" OR "head of product marketing" OR "VP product marketing"'
            team_q   = co + ' "product marketing" manager'
        elif 'brand' in t:
            peer_q   = co + ' "brand manager" OR "brand marketing manager"'
            mgr_q    = co + ' "brand director" OR "head of brand" OR "director of brand marketing"'
            team_q   = co + ' "brand marketing" manager'
        elif 'gtm' in t or 'go to market' in t:
            peer_q   = co + ' "go to market manager" OR "GTM manager"'
            mgr_q    = co + ' "director of marketing" OR "head of marketing" OR "VP marketing"'
            team_q   = co + ' "growth marketing" OR "demand generation"'
        elif 'integrated' in t or 'campaign' in t:
            peer_q   = co + ' "integrated marketing manager" OR "campaign manager"'
            mgr_q    = co + ' "director of integrated marketing" OR "head of marketing"'
            team_q   = co + ' "marketing communications" manager'
        elif 'growth' in t or 'demand' in t:
            peer_q   = co + ' "growth marketing manager" OR "demand generation manager"'
            mgr_q    = co + ' "VP growth" OR "director of growth" OR "head of growth"'
            team_q   = co + ' "growth marketing" OR "performance marketing"'
        else:
            peer_q   = co + ' "marketing manager"'
            mgr_q    = co + ' "marketing director" OR "head of marketing" OR "VP marketing"'
            team_q   = co + ' marketing manager'

        recruiter_q = co + ' recruiter "marketing" OR "talent acquisition" marketing'
        alumni_q    = '"Babson" ' + co

        return [
            ('Same-Role Peers at ' + company,    url(peer_q),     '&#128101;'),
            ('Hiring Manager (Director / Head)',  url(mgr_q),      '&#128084;'),
            ('Marketing Leadership at co.',       url(team_q),     '&#127775;'),
            ('Recruiter for Marketing roles',     url(recruiter_q),'&#128203;'),
            ('Babson Alumni at ' + company,       url(alumni_q),   '&#127891;'),
        ]

    def connection_request(self, company, title, matched):
        skill = next((s for s in matched
                      if s not in ('MBA preferred/required', 'Strong title alignment')), 'brand and GTM marketing')
        msg = ('Hi [Name], I\'m a Babson MBA focused on ' + skill.lower() +
               ' and came across ' + company + '\'s ' + title + ' opening. '
               'Would love to connect and hear about your experience on the team!')
        return msg[:295]

    def inmail_template(self, company, title, matched):
        skills = [s for s in matched if s not in ('MBA preferred/required', 'Strong title alignment')]
        skills_str = ' and '.join(skills[:2]) if skills else 'brand strategy and go-to-market execution'
        return [
            'Hi [Name],',
            'I came across the ' + title + ' role at ' + company
            + ' and was genuinely excited — it maps closely to my background in '
            + skills_str + '.',
            'I\'m a Babson MBA (Marketing & Entrepreneurship, May 2026) with '
            'experience in GTM strategy, consumer insights research, and B2B marketing. '
            'I recently built a full segmentation-to-launch GTM plan for a Gates Foundation '
            'project and conducted consumer research across 52 families for a nonprofit.',
            'I\'d love to hear what success looks like in this role at ' + company
            + '. Would you be open to a quick 15-min chat? No pressure at all.',
            'Thank you so much — Prachita',
        ]

    # ── JD scraping ───────────────────────────────────────────────────

    def scrape_job_description(self, url):
        try:
            time.sleep(random.uniform(1, 2))
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
        for p in patterns:
            for m in re.finditer(p, text):
                try: years_found.append(int(m.group(1)))
                except: continue
        return min(years_found) if years_found else None

    def extract_salary(self, description):
        m = re.search(r'\$[\d,]+\s*(?:k|K)?\s*(?:-|to)\s*\$[\d,]+\s*(?:k|K)?', description)
        return m.group(0) if m else None

    def extract_key_skills(self, description):
        lines = [l.strip() for l in description.split('\n') if l.strip()]
        qual_kw = ['qualifications', 'requirements', 'what you', 'you bring', 'you have', 'about you']
        start = 0
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in qual_kw):
                start = i + 1
                break
        snippets = []
        for line in lines[start:start + 15]:
            if 10 < len(line) < 200 and not any(
                s in line.lower() for s in ['equal opportunity', 'we are an', 'salary', 'compensation']
            ):
                snippets.append(line.lstrip('•-– ').strip())
            if len(snippets) == 5:
                break
        return snippets

    def enrich_with_jd(self, jobs):
        jobs = jobs[:40]
        enriched, total = [], len(jobs)
        for idx, job in enumerate(jobs, 1):
            print("  JD [" + str(idx) + "/" + str(total) + "] " + job['title'] + " @ " + job['company'])
            desc = self.scrape_job_description(job['url'])
            min_yrs = self.extract_min_years(desc)
            if min_yrs is not None and min_yrs > self.max_years_experience:
                print("    Filtered — requires " + str(min_yrs) + "+ yrs")
                continue
            job['years_required'] = (str(min_yrs) + "+ years") if min_yrs else "Not specified"
            job['key_skills'] = self.extract_key_skills(desc)
            job['salary']     = self.extract_salary(desc)
            self.score_job_by_resume(job, desc)
            enriched.append(job)
            print("    Kept — " + job['match_label'] + " (" + str(job['relevance_score']) + "/10)")
        print("JD filter: kept " + str(len(enriched)) + " of " + str(total))
        return enriched

    # ── Search ────────────────────────────────────────────────────────

    def scrape_jobs_for_keyword(self, keyword):
        params = {
            'keywords': keyword, 'location': 'United States',
            'f_TPR': 'r86400', 'f_E': '3,4', 'position': 1, 'pageNum': 0
        }
        try:
            time.sleep(random.uniform(2, 3))
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []
            for card in soup.find_all('div', class_='base-card')[:12]:
                try:
                    job_id    = card.get('data-entity-urn', '').split(':')[-1]
                    title_el  = card.find('h3', class_='base-search-card__title')
                    co_el     = card.find('h4', class_='base-search-card__subtitle')
                    loc_el    = card.find('span', class_='job-search-card__location')
                    link_el   = card.find('a', class_='base-card__full-link')
                    if title_el and co_el and link_el:
                        title = title_el.text.strip()
                        if self.is_senior_role(title): continue
                        jobs.append({
                            'id': job_id or link_el.get('href','').split('?')[0].split('/')[-1],
                            'title': title,
                            'company': co_el.text.strip(),
                            'location': loc_el.text.strip() if loc_el else 'United States',
                            'url': link_el.get('href','').split('?')[0],
                            'found_date': datetime.now().isoformat(),
                            'search_keyword': keyword,
                        })
                except Exception: continue
            return jobs
        except Exception:
            print("Error scraping " + keyword)
            return []

    def scrape_jobs(self):
        all_jobs = []
        print("Searching " + str(len(self.search_keywords)) + " keywords across all US locations...")
        for idx, kw in enumerate(self.search_keywords, 1):
            print("  [" + str(idx) + "/" + str(len(self.search_keywords)) + "] " + kw)
            jobs = self.scrape_jobs_for_keyword(kw)
            print("      Found " + str(len(jobs)) + " jobs")
            all_jobs.extend(jobs)
        unique = {}
        for job in all_jobs:
            if job['id'] not in unique: unique[job['id']] = job
        print("Total unique (pre-JD filter): " + str(len(unique)))
        return list(unique.values())

    def find_new_jobs(self, current_jobs, existing_jobs):
        return [j for j in current_jobs if j['id'] not in existing_jobs]

    # ── Email ─────────────────────────────────────────────────────────

    def send_email_notification(self, new_jobs):
        if not new_jobs:
            print("No new jobs found"); return

        sender_email    = os.environ.get('SENDER_EMAIL')
        sender_password = os.environ.get('SENDER_PASSWORD')
        recipient_email = os.environ.get('RECIPIENT_EMAIL', sender_email)
        if not sender_email or not sender_password:
            print("Email credentials not found"); return

        sorted_jobs = sorted(
            [j for j in new_jobs if j.get('relevance_score', 0) > 5],
            key=lambda j: j.get('relevance_score', 0), reverse=True
        )
        if not sorted_jobs:
            print("No jobs with score > 5"); return

        excellent = [j for j in sorted_jobs if j.get('relevance_score', 0) >= 8]
        strong    = [j for j in sorted_jobs if 6 <= j.get('relevance_score', 0) < 8]

        subject = "Job Alert: " + str(len(sorted_jobs)) + " New PMM/Brand/GTM Roles — Ranked by Resume Fit"

        bp = []
        bp.append('<html><body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,sans-serif;">'
                  '<div style="max-width:700px;margin:24px auto;background:#fff;border-radius:8px;'
                  'overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">')

        # Header
        bp.append('<div style="background:#0073b1;padding:24px 28px;">'
                  '<h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">PMM &amp; Brand Job Alert</h1>'
                  '<p style="margin:6px 0 0;color:#cce4f6;font-size:13px;">'
                  + str(len(sorted_jobs)) + ' roles scored &gt;5/10 &bull; Sorted by resume match &bull; '
                  'Outreach included per job</p></div>')

        # Summary table
        bp.append('<div style="padding:20px 28px 10px;">'
                  '<h2 style="margin:0 0 12px;font-size:14px;color:#333;border-bottom:1px solid #e0e0e0;padding-bottom:8px;">At a Glance</h2>'
                  '<table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;border-collapse:collapse;">'
                  '<tr style="background:#f4f6f8;color:#555;">'
                  '<th align="left" style="padding:7px 8px;border-bottom:1px solid #ddd;">#</th>'
                  '<th align="left" style="padding:7px 8px;border-bottom:1px solid #ddd;">Role &amp; Company</th>'
                  '<th align="left" style="padding:7px 8px;border-bottom:1px solid #ddd;">Location</th>'
                  '<th align="left" style="padding:7px 8px;border-bottom:1px solid #ddd;">Exp.</th>'
                  '<th align="center" style="padding:7px 8px;border-bottom:1px solid #ddd;">Score</th>'
                  '</tr>')
        for i, job in enumerate(sorted_jobs, 1):
            sc = job.get('relevance_score', 0)
            lc = job.get('label_color', '#5f6368')
            lb = job.get('label_bg',    '#f1f3f4')
            bg = '#fff' if i % 2 == 0 else '#fafafa'
            bp.append('<tr style="background:' + bg + ';">'
                      '<td style="padding:6px 8px;color:#888;">' + str(i) + '</td>'
                      '<td style="padding:6px 8px;"><a href="' + str(job.get('url','')) + '" style="color:#0073b1;text-decoration:none;font-weight:600;">'
                      + self.clean_text(job.get('title','')) + '</a><br>'
                      '<span style="color:#666;font-size:11px;">' + self.clean_text(job.get('company','')) + '</span></td>'
                      '<td style="padding:6px 8px;color:#555;font-size:11px;">' + self.clean_text(job.get('location','')) + '</td>'
                      '<td style="padding:6px 8px;color:#555;font-size:11px;">' + self.clean_text(job.get('years_required','?')) + '</td>'
                      '<td align="center" style="padding:6px 8px;">'
                      '<span style="background:' + lb + ';color:' + lc + ';font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;">'
                      + str(sc) + '/10</span></td></tr>')
        bp.append('</table></div>')

        # ── Job card + outreach per job ───────────────────────────────
        def section_hdr(label, color, bg):
            bp.append('<div style="margin:20px 28px 0;padding:8px 12px;background:' + bg + ';'
                      'border-left:4px solid ' + color + ';border-radius:0 4px 4px 0;">'
                      '<span style="font-size:13px;font-weight:700;color:' + color + ';">' + label + '</span></div>')

        def render_job(job, idx):
            sc      = job.get('relevance_score', 0)
            ml      = job.get('match_label', '')
            lc      = job.get('label_color', '#5f6368')
            lb      = job.get('label_bg',    '#f1f3f4')
            matched = job.get('matched_skills', [])
            skills  = job.get('key_skills', [])
            salary  = self.clean_text(job.get('salary','')) or None
            company = self.clean_text(job.get('company',''))
            title   = self.clean_text(job.get('title',''))
            url     = str(job.get('url',''))
            accent  = '#137333' if sc >= 8 else ('#1a73e8' if sc >= 6 else '#e37400')
            display_matched = [s for s in matched if s not in ('MBA preferred/required', 'Strong title alignment')]
            links   = self.people_search_links(company, title)
            conn    = self.connection_request(company, title, matched)
            inmail  = self.inmail_template(company, title, matched)

            # ── ONE unified card ──────────────────────────────────────
            bp.append('<div style="margin:12px 28px 16px;border:1px solid #dde3ec;'
                      'border-left:4px solid ' + accent + ';border-radius:6px;'
                      'overflow:hidden;background:#fff;">')

            # ── Full-width header row ─────────────────────────────────
            bp.append('<table width="100%" cellpadding="0" cellspacing="0">'
                      '<tr style="background:#f8f9fc;border-bottom:1px solid #e8ecf2;">'
                      '<td style="padding:12px 16px;vertical-align:middle;">'
                      '<span style="font-size:14px;font-weight:700;color:#0073b1;">'
                      + str(idx) + '. ' + title + '</span><br>'
                      '<span style="font-size:12px;color:#555;">'
                      + company + ' &bull; ' + self.clean_text(job.get('location','')) + '</span>'
                      '</td>'
                      '<td align="right" style="padding:12px 16px;vertical-align:middle;white-space:nowrap;">'
                      '<span style="background:' + lb + ';color:' + lc + ';font-size:11px;font-weight:700;'
                      'padding:4px 12px;border-radius:12px;">' + ml + ' &bull; ' + str(sc) + '/10</span>'
                      '</td></tr></table>')

            # ── Two-column body ───────────────────────────────────────
            bp.append('<table width="100%" cellpadding="0" cellspacing="0"><tr>')

            # LEFT: job details (54%)
            bp.append('<td width="54%" valign="top" style="padding:14px 16px;'
                      'border-right:1px solid #e8ecf2;vertical-align:top;">')

            # Meta pills
            bp.append('<p style="margin:0 0 8px;">'
                      '<span style="background:#f1f3f4;color:#444;font-size:11px;'
                      'padding:2px 8px;border-radius:10px;margin-right:6px;">'
                      'Exp: ' + self.clean_text(job.get('years_required','Not specified')) + '</span>')
            if salary:
                bp.append('<span style="background:#edf7ed;color:#137333;font-size:11px;'
                          'padding:2px 8px;border-radius:10px;">' + salary + '</span>')
            bp.append('</p>')

            # Matched skills chips
            if display_matched:
                bp.append('<p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#444;">'
                          'Your skills this role values:</p><p style="margin:0 0 8px;">')
                for s in display_matched:
                    bp.append('<span style="display:inline-block;background:#e6f4ea;color:#137333;'
                              'font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;'
                              'margin:2px 3px 2px 0;">&#10003; ' + self.clean_text(s) + '</span>')
                bp.append('</p>')

            # Key JD requirements
            if skills:
                bp.append('<p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#444;">'
                          'What they need:</p>'
                          '<ul style="margin:0 0 10px;padding-left:14px;font-size:11px;color:#555;line-height:1.7;">')
                for s in skills:
                    bp.append('<li>' + self.clean_text(s) + '</li>')
                bp.append('</ul>')

            # Apply button
            bp.append('<a href="' + url + '" style="display:inline-block;background:#0073b1;color:#fff;'
                      'font-size:11px;font-weight:700;padding:6px 14px;border-radius:4px;'
                      'text-decoration:none;">Apply Now &rarr;</a>'
                      '<span style="font-size:10px;color:#bbb;margin-left:10px;">Found: '
                      + str(job.get('found_date',''))[:10] + '</span>')
            bp.append('</td>')  # end left column

            # RIGHT: outreach (46%)
            bp.append('<td width="46%" valign="top" style="padding:14px 14px;'
                      'background:#f8faff;vertical-align:top;">')

            # People to reach out to
            bp.append('<p style="margin:0 0 6px;font-size:11px;font-weight:700;color:#0073b1;">'
                      '&#128269; Who to reach out to</p>'
                      '<table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:10px;">')
            for (lbl, href, icon) in links:
                bp.append('<tr><td style="padding:2px 0;font-size:10px;color:#555;width:10px;">'
                          + icon + '</td>'
                          '<td style="padding:2px 4px;">'
                          '<a href="' + href + '" style="font-size:10px;color:#0073b1;'
                          'text-decoration:none;font-weight:600;">' + self.clean_text(lbl) + '</a>'
                          '</td></tr>')
            bp.append('</table>')

            # Connection request
            bp.append('<p style="margin:0 0 3px;font-size:11px;font-weight:700;color:#333;">'
                      '&#9993; Connection Request '
                      '<span style="font-weight:400;color:#888;font-size:10px;">(&lt;300 chars)</span></p>'
                      '<div style="background:#fff;border:1px solid #dde3f0;border-radius:4px;'
                      'padding:8px 10px;font-size:10px;color:#333;line-height:1.6;margin-bottom:8px;">'
                      + self.clean_text(conn) + '</div>')

            # InMail
            bp.append('<p style="margin:0 0 3px;font-size:11px;font-weight:700;color:#333;">'
                      '&#128231; LinkedIn InMail</p>'
                      '<div style="background:#fff;border:1px solid #dde3f0;border-radius:4px;'
                      'padding:8px 10px;">')
            for line in inmail:
                bp.append('<p style="margin:3px 0;font-size:10px;color:#333;line-height:1.6;">'
                          + self.clean_text(line) + '</p>')
            bp.append('</div>')

            bp.append('</td></tr></table>')  # end two-column body
            bp.append('</div>')              # end unified card

        # Render by section
        if excellent:
            section_hdr('Excellent Match — ' + str(len(excellent)) + ' role(s)  (8-10/10)', '#137333', '#e6f4ea')
            for i, job in enumerate(excellent, 1):
                render_job(job, i)

        if strong:
            section_hdr('Strong Match — ' + str(len(strong)) + ' role(s)  (6-7/10)', '#1a73e8', '#e8f0fe')
            for i, job in enumerate(strong, len(excellent) + 1):
                render_job(job, i)

        # Footer
        bp.append('<div style="padding:16px 28px;background:#f4f6f8;margin-top:8px;">'
                  '<p style="margin:0;font-size:11px;color:#999;line-height:1.6;">'
                  'Entry &amp; manager level only &bull; JD-verified (max 4 yrs exp) &bull; All US locations &bull; '
                  'Scored against Prachita\'s resume (11 signals) &bull; Updated every 2 hrs, 7 AM-9 PM EST'
                  '</p></div></div></body></html>')

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = sender_email
        msg['To']      = recipient_email
        msg.attach(MIMEText("".join(bp), 'html', 'utf-8'))

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
            print("EMAIL SENT — " + str(len(sorted_jobs)) + " jobs")
        except Exception as e:
            print("Error sending email: " + str(e))

    # ── Static webpage generator ─────────────────────────────────────

    def generate_html(self, all_jobs_dict):
        jobs_for_page = sorted(
            [j for j in all_jobs_dict.values() if j.get('relevance_score', 0) > 5],
            key=lambda j: j.get('relevance_score', 0), reverse=True
        )
        now_str   = datetime.now().strftime('%b %d, %Y at %I:%M %p UTC')
        total     = len(jobs_for_page)
        n_exc     = sum(1 for j in jobs_for_page if j.get('relevance_score',0) >= 8)
        n_str     = sum(1 for j in jobs_for_page if 6 <= j.get('relevance_score',0) < 8)
        companies = len(set(j.get('company','') for j in jobs_for_page))

        clean = []
        for job in jobs_for_page:
            co    = self.clean_text(job.get('company',''))
            ti    = self.clean_text(job.get('title',''))
            mat   = job.get('matched_skills', [])
            links = self.people_search_links(co, ti)
            clean.append({
                'title':    ti,
                'company':  co,
                'location': self.clean_text(job.get('location','')),
                'url':      job.get('url',''),
                'score':    job.get('relevance_score', 0),
                'label':    job.get('match_label',''),
                'skills':   [self.clean_text(s) for s in mat
                             if s not in ('MBA preferred/required','Strong title alignment')],
                'needs':    [self.clean_text(s) for s in job.get('key_skills',[])],
                'exp':      self.clean_text(job.get('years_required','Not specified')),
                'salary':   self.clean_text(job.get('salary','')),
                'date':     str(job.get('found_date',''))[:10],
                'people':   [{'label': l, 'url': h, 'icon': ic} for l,h,ic in links],
                'conn':     self.clean_text(self.connection_request(co, ti, mat)),
                'inmail':   [self.clean_text(x) for x in self.inmail_template(co, ti, mat)],
            })

        jobs_json = json.dumps(clean, ensure_ascii=True)

        TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Dashboard — Prachita Purohit</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@700;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#080c14;--s1:rgba(255,255,255,0.04);--s2:rgba(255,255,255,0.07);--bd:rgba(255,255,255,0.08);--bdg:rgba(129,140,248,0.3);--tx:#e2e8f0;--mu:#64748b;--di:#94a3b8;--em:#10b981;--in:#818cf8;--am:#f59e0b}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--tx);min-height:100vh;background-image:radial-gradient(circle,rgba(99,102,241,.055) 1px,transparent 1px);background-size:28px 28px}
/* HERO */
.hero{position:relative;padding:64px 32px 48px;text-align:center;background:radial-gradient(ellipse 80% 50% at 50% 0%,rgba(99,102,241,.14) 0%,transparent 100%);border-bottom:1px solid var(--bd);overflow:hidden}
.hero::after{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 50% 40% at 80% 110%,rgba(236,72,153,.07) 0%,transparent 100%);pointer-events:none}
.eyebrow{display:inline-flex;align-items:center;gap:7px;font-size:11px;font-weight:700;color:var(--in);background:rgba(129,140,248,.1);border:1px solid rgba(129,140,248,.2);border-radius:100px;padding:5px 16px;margin-bottom:22px;letter-spacing:.06em;text-transform:uppercase}
.dot-live{width:6px;height:6px;background:var(--em);border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.75)}}
.hero h1{font-family:'Space Grotesk',sans-serif;font-size:clamp(36px,6vw,70px);font-weight:800;letter-spacing:-.04em;line-height:1.05;background:linear-gradient(135deg,#fff 15%,#a78bfa 52%,#ec4899 90%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:14px}
.hero-sub{font-size:14px;color:var(--mu);margin-bottom:36px}
.hero-sub b{color:var(--di);font-weight:500}
/* STATS */
.stats-row{display:flex;justify-content:center;gap:14px;flex-wrap:wrap}
.sc{background:var(--s1);border:1px solid var(--bd);border-radius:16px;padding:16px 26px;text-align:center;backdrop-filter:blur(12px)}
.sc-n{font-size:32px;font-weight:800;line-height:1;margin-bottom:5px}
.sc-n.g{background:linear-gradient(135deg,#818cf8,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.sc-n.e{color:var(--em)}.sc-n.i{color:var(--in)}
.sc-l{font-size:10px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.07em}
/* FILTER BAR */
.fbar{position:sticky;top:0;z-index:100;padding:11px 32px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:rgba(8,12,20,.88);backdrop-filter:blur(22px);border-bottom:1px solid var(--bd)}
.srch-wrap{position:relative;flex:1;min-width:180px;max-width:280px}
.srch-ico{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--mu);width:14px;height:14px;pointer-events:none}
.srch{width:100%;background:var(--s1);border:1px solid var(--bd);border-radius:100px;padding:8px 16px 8px 36px;color:var(--tx);font-size:12px;font-family:inherit;outline:none;transition:.2s}
.srch::placeholder{color:var(--mu)}
.srch:focus{border-color:rgba(129,140,248,.5);box-shadow:0 0 0 3px rgba(99,102,241,.1);background:var(--s2)}
.fdiv{width:1px;height:22px;background:var(--bd);flex-shrink:0}
.pg{display:flex;gap:5px;flex-wrap:wrap}
.fp{padding:6px 15px;border-radius:100px;border:1px solid var(--bd);background:transparent;color:var(--mu);font-size:12px;font-weight:600;font-family:inherit;cursor:pointer;transition:.18s;white-space:nowrap}
.fp:hover:not(.active){border-color:rgba(129,140,248,.4);color:var(--di)}
.fp.active{background:linear-gradient(135deg,#6366f1,#8b5cf6);border-color:transparent;color:#fff;box-shadow:0 0 18px rgba(99,102,241,.35)}
.ts{margin-left:auto;font-size:11px;color:var(--mu);white-space:nowrap}
/* RESULT BAR */
.rbar{padding:10px 32px;font-size:12px;color:var(--mu)}
.rbar b{color:var(--di)}
/* GRID */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:20px;padding:16px 32px 56px;max-width:1440px;margin:0 auto}
/* CARD */
.card{position:relative;background:var(--s1);border:1px solid var(--bd);border-radius:20px;overflow:hidden;transition:transform .22s ease,box-shadow .22s ease,border-color .22s ease;backdrop-filter:blur(14px);display:flex;flex-direction:column}
.card:hover{transform:translateY(-5px);border-color:var(--bdg);box-shadow:0 24px 64px rgba(0,0,0,.5),0 0 0 1px rgba(129,140,248,.12),inset 0 1px 0 rgba(255,255,255,.05)}
.cstripe{height:3px}
.se{background:linear-gradient(90deg,#059669,#10b981,#34d399)}
.si{background:linear-gradient(90deg,#4f46e5,#818cf8,#a78bfa)}
.sa{background:linear-gradient(90deg,#d97706,#f59e0b,#fbbf24)}
.cbody{padding:20px;flex:1;display:flex;flex-direction:column;gap:13px}
/* Score ring */
.trow{display:flex;align-items:flex-start;gap:14px}
.rwrap{position:relative;width:56px;height:56px;flex-shrink:0}
.rwrap svg{display:block}
.rnum{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:800;line-height:1}
.tblock{flex:1;min-width:0}
.mbadge{display:inline-block;font-size:10px;font-weight:700;padding:2px 10px;border-radius:100px;margin-bottom:6px;letter-spacing:.04em;text-transform:uppercase}
.be{background:rgba(16,185,129,.12);color:#34d399;border:1px solid rgba(16,185,129,.2)}
.bi{background:rgba(129,140,248,.12);color:#a78bfa;border:1px solid rgba(129,140,248,.2)}
.ba{background:rgba(245,158,11,.12);color:#fbbf24;border:1px solid rgba(245,158,11,.2)}
.jtitle{font-size:14px;font-weight:700;line-height:1.3;margin-bottom:3px}
.jtitle a{color:var(--tx);text-decoration:none;transition:.15s}
.jtitle a:hover{color:#a78bfa}
.jmeta{font-size:11px;color:var(--mu);display:flex;gap:5px;flex-wrap:wrap;align-items:center}
.jdot{color:rgba(255,255,255,.12)}
/* Chips */
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{font-size:10px;font-weight:600;padding:3px 10px;border-radius:100px;background:rgba(16,185,129,.1);color:#34d399;border:1px solid rgba(16,185,129,.15)}
.chip::before{content:"\\2713  "}
/* Needs */
.nlbl{font-size:10px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px}
.nlist{list-style:none;display:flex;flex-direction:column;gap:4px}
.nlist li{font-size:12px;color:var(--di);padding-left:14px;position:relative;line-height:1.5}
.nlist li::before{content:"\\203A";position:absolute;left:0;color:#818cf8;font-weight:700}
/* Pills */
.mpills{display:flex;gap:6px;flex-wrap:wrap}
.mp{font-size:11px;padding:3px 10px;border-radius:100px;background:var(--s2);color:var(--di);border:1px solid var(--bd);font-weight:500}
.mps{background:rgba(16,185,129,.08);color:#34d399;border-color:rgba(16,185,129,.15)}
/* Actions */
.cact{display:flex;gap:8px;margin-top:auto;padding-top:2px}
.baply{padding:9px 20px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border:none;border-radius:10px;font-size:12px;font-weight:700;font-family:inherit;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:5px;transition:.18s;box-shadow:0 4px 14px rgba(99,102,241,.3)}
.baply:hover{box-shadow:0 6px 22px rgba(99,102,241,.45);transform:translateY(-1px)}
.brch{flex:1;padding:9px 14px;background:var(--s2);color:var(--di);border:1px solid var(--bd);border-radius:10px;font-size:12px;font-weight:600;font-family:inherit;cursor:pointer;transition:.18s}
.brch:hover{border-color:rgba(129,140,248,.4);color:var(--in)}
.brch.open{background:rgba(129,140,248,.12);border-color:rgba(129,140,248,.3);color:#a78bfa}
/* Outreach panel */
.outreach{max-height:0;overflow:hidden;transition:max-height .45s ease}
.outreach.open{max-height:1400px}
.oin{padding:18px 20px;display:flex;flex-direction:column;gap:14px;background:rgba(0,0,0,.25);border-top:1px solid var(--bd)}
.olbl{font-size:10px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.08em;margin-bottom:7px}
.plinks{display:flex;flex-direction:column;gap:3px}
.plink{display:flex;align-items:center;gap:10px;padding:7px 10px;border-radius:8px;text-decoration:none;color:var(--di);font-size:12px;border:1px solid transparent;transition:.15s}
.plink:hover{background:rgba(129,140,248,.08);border-color:rgba(129,140,248,.15);color:#a78bfa}
.pi{font-size:14px;width:20px;text-align:center}
.pa{margin-left:auto;font-size:10px;opacity:.4}
.tbox{position:relative;background:rgba(0,0,0,.3);border:1px solid var(--bd);border-radius:10px;padding:12px 14px;padding-right:68px;font-size:12px;color:var(--di);line-height:1.7}
.tbox p{margin-bottom:4px}.tbox p:last-child{margin-bottom:0}
.cpb{position:absolute;top:10px;right:10px;padding:3px 10px;font-size:10px;font-weight:700;border:1px solid var(--bd);border-radius:6px;background:var(--s2);color:var(--mu);cursor:pointer;font-family:inherit;transition:.15s}
.cpb:hover{background:#6366f1;color:#fff;border-color:#6366f1}
.cpb.ok{background:#059669;color:#fff;border-color:#059669}
/* Applied state */
.card-applied{border-color:rgba(16,185,129,.35) !important;box-shadow:0 0 0 1px rgba(16,185,129,.12)}
.card-applied .cstripe{background:linear-gradient(90deg,#059669,#10b981,#34d399) !important}
.applied-tag{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:700;padding:2px 10px;border-radius:100px;background:rgba(16,185,129,.15);color:#34d399;border:1px solid rgba(16,185,129,.25);margin-left:auto;white-space:nowrap}
.bapl{padding:9px 16px;background:var(--s2);color:var(--di);border:1px solid var(--bd);border-radius:10px;font-size:12px;font-weight:600;font-family:inherit;cursor:pointer;transition:.18s;white-space:nowrap}
.bapl:hover{border-color:rgba(16,185,129,.4);color:var(--em)}
.bapl.done{background:rgba(16,185,129,.12);border-color:rgba(16,185,129,.3);color:#34d399}
/* No results */
.nr{grid-column:1/-1;text-align:center;padding:80px 20px;color:var(--mu)}
.nr h3{font-size:20px;color:var(--di);margin-bottom:8px}
/* Footer */
.footer{text-align:center;padding:24px;font-size:11px;color:var(--mu);border-top:1px solid var(--bd)}
@media(max-width:640px){.hero{padding:40px 20px 32px}.fbar{padding:10px 16px}.grid{padding:14px;gap:14px}.sc{padding:12px 18px}}
</style>
</head>
<body>

<section class="hero">
  <div class="eyebrow"><span class="dot-live"></span>Live Job Dashboard</div>
  <h1>Will get you a job bitch</h1>
  <p class="hero-sub">Scored against Prachita&#39;s resume &bull; Entry &amp; manager level &bull; <b>Auto-updates every 2 hrs</b></p>
  <div class="stats-row">
    <div class="sc"><div class="sc-n g">__TOTAL__</div><div class="sc-l">Total Roles</div></div>
    <div class="sc"><div class="sc-n e">__EXC__</div><div class="sc-l">Excellent 8+</div></div>
    <div class="sc"><div class="sc-n i">__STR__</div><div class="sc-l">Strong 6-7</div></div>
    <div class="sc"><div class="sc-n g">__COS__</div><div class="sc-l">Companies</div></div>
  </div>
</section>

<div class="fbar">
  <div class="srch-wrap">
    <svg class="srch-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
    <input class="srch" id="srch" type="text" placeholder="Search role or company&#8230;" oninput="render()">
  </div>
  <div class="fdiv"></div>
  <div class="pg" id="sg">
    <button class="fp active" onclick="sf('score','all',this,'sg')">All</button>
    <button class="fp" onclick="sf('score','6',this,'sg')">Score 6+</button>
    <button class="fp" onclick="sf('score','8',this,'sg')">Score 8+</button>
  </div>
  <div class="fdiv"></div>
  <div class="pg" id="rg">
    <button class="fp active" onclick="sf('role','all',this,'rg')">All Roles</button>
    <button class="fp" onclick="sf('role','brand',this,'rg')">Brand</button>
    <button class="fp" onclick="sf('role','pmm',this,'rg')">PMM</button>
    <button class="fp" onclick="sf('role','gtm',this,'rg')">GTM</button>
    <button class="fp" onclick="sf('role','growth',this,'rg')">Growth</button>
    <button class="fp" onclick="sf('role','applied',this,'rg')" id="applied-pill">&#10003; Applied (<span id="applied-count">0</span>)</button>
  </div>
  <div class="fdiv"></div>
  <div class="pg" id="sortg">
    <button class="fp active" onclick="sf('sort','score',this,'sortg')">&#9733; Top Match</button>
    <button class="fp" onclick="sf('sort','recent',this,'sortg')">&#128336; Most Recent</button>
  </div>
  <span class="ts">__NOW__</span>
</div>

<div class="rbar" id="rbar"></div>
<div class="grid" id="grid"></div>

<footer class="footer">Entry &amp; manager level only &bull; JD-verified (max 4 yrs exp) &bull; All US locations &bull; Scored on 11 resume signals &bull; Auto-updates every 2 hrs, 7 AM&ndash;9 PM EST</footer>

<script>
const JOBS=__JOBS__;
let F={score:'all',role:'all',sort:'score'};
function sf(k,v,el,gid){F[k]=v;document.getElementById(gid).querySelectorAll('.fp').forEach(b=>b.classList.remove('active'));el.classList.add('active');render();}
function getApplied(){return new Set(JSON.parse(localStorage.getItem('ljs_applied')||'[]'));}
function saveApplied(s){localStorage.setItem('ljs_applied',JSON.stringify([...s]));}
function updateAppliedCount(){const n=getApplied().size;const el=document.getElementById('applied-count');if(el)el.textContent=n;}
function toggleApplied(url,i){
  const s=getApplied();
  const card=document.getElementById('card-'+i);
  const btn=document.getElementById('apl-'+i);
  if(s.has(url)){s.delete(url);if(card)card.classList.remove('card-applied');if(btn){btn.textContent='Mark Applied';btn.classList.remove('done');}}
  else{s.add(url);if(card)card.classList.add('card-applied');if(btn){btn.textContent='\\u2713 Applied';btn.classList.add('done');}}
  saveApplied(s);updateAppliedCount();
  if(F.role==='applied')render();
}
function ring(s){
  const r=22,c=2*Math.PI*r,off=c*(1-s/10);
  const col=s>=8?'#10b981':s>=6?'#818cf8':'#f59e0b';
  const sc=s>=8?'se':s>=6?'si':'sa';
  const bc=s>=8?'be':s>=6?'bi':'ba';
  const svg=`<div class="rwrap"><svg width="56" height="56" viewBox="0 0 56 56"><circle cx="28" cy="28" r="${r}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="4"/><circle cx="28" cy="28" r="${r}" fill="none" stroke="${col}" stroke-width="4" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}" stroke-linecap="round" style="transform:rotate(-90deg);transform-origin:28px 28px"/></svg><div class="rnum" style="color:${col}">${s}</div></div>`;
  return {col,sc,bc,svg};
}
function esc(t){return(t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function rm(title,role){
  if(role==='all')return true;
  const t=title.toLowerCase();
  if(role==='brand')return t.includes('brand');
  if(role==='pmm')return t.includes('product marketing');
  if(role==='gtm')return t.includes('gtm')||t.includes('go to market');
  if(role==='growth')return t.includes('growth')||t.includes('demand');
  return true;
}
function cp(id,btn){
  const el=document.getElementById(id);
  navigator.clipboard.writeText(el.innerText).then(()=>{btn.textContent='Copied!';btn.classList.add('ok');setTimeout(()=>{btn.textContent='Copy';btn.classList.remove('ok');},2000);});
}
function tog(i){
  const p=document.getElementById('o'+i),b=document.getElementById('r'+i);
  const open=p.classList.toggle('open');
  b.textContent=open?'Close ✕':'Reach Out ↓';
  b.classList.toggle('open',open);
}
function render(){
  const q=document.getElementById('srch').value.toLowerCase();
  const applied=getApplied();
  updateAppliedCount();
  let list=JOBS.filter(j=>{
    if(F.role==='applied')return applied.has(j.url);
    if(F.score!=='all'&&j.score<parseInt(F.score))return false;
    if(!rm(j.title,F.role))return false;
    if(q&&!j.title.toLowerCase().includes(q)&&!j.company.toLowerCase().includes(q))return false;
    return true;
  });
  if(F.sort==='recent'){list=[...list].sort((a,b)=>(b.date||'').localeCompare(a.date||''));}
  else{list=[...list].sort((a,b)=>b.score-a.score);}
  document.getElementById('rbar').innerHTML=`Showing <b>${list.length}</b> of <b>${JOBS.length}</b> roles`;
  const grid=document.getElementById('grid');
  if(!list.length){grid.innerHTML='<div class="nr"><h3>No roles found</h3><p>Try a different filter or search.</p></div>';return;}
  grid.innerHTML=list.map((j,i)=>{
    const {sc,bc,svg}=ring(j.score);
    const lbl=j.label||(j.score>=8?'Excellent Match':j.score>=6?'Strong Match':'Good Match');
    const chips=(j.skills||[]).map(s=>`<span class="chip">${esc(s)}</span>`).join('');
    const needs=(j.needs||[]).map(n=>`<li>${esc(n)}</li>`).join('');
    const pills=`<span class="mp">${esc(j.exp||'Exp N/A')}</span>`+(j.salary?`<span class="mp mps">${esc(j.salary)}</span>`:'')+`<span class="mp">${esc(j.date)}</span>`;
    const people=(j.people||[]).map(p=>`<a class="plink" href="${esc(p.url)}" target="_blank" rel="noopener"><span class="pi">${p.icon}</span><span>${esc(p.label)}</span><span class="pa">&#8599;</span></a>`).join('');
    const cid='c'+i,mid='m'+i;
    const inmail=(j.inmail||[]).map(l=>`<p>${esc(l)}</p>`).join('');
    const isApl=applied.has(j.url);
    const aplBtn=`<button class="bapl${isApl?' done':''}" id="apl-${i}" onclick="toggleApplied('${esc(j.url)}',${i})">${isApl?'\\u2713 Applied':'Mark Applied'}</button>`;
    const aplTag=isApl?'<span class="applied-tag">\\u2713 Applied</span>':'';
    return `<div class="card${isApl?' card-applied':''}" id="card-${i}"><div class="cstripe ${sc}"></div><div class="cbody"><div class="trow">${svg}<div class="tblock"><div style="display:flex;align-items:flex-start;gap:6px;flex-wrap:wrap"><div class="mbadge ${bc}">${esc(lbl)}</div>${aplTag}</div><div class="jtitle"><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a></div><div class="jmeta"><span>${esc(j.company)}</span><span class="jdot">&bull;</span><span>${esc(j.location)}</span></div></div></div>${chips?`<div class="chips">${chips}</div>`:''}${needs?`<div><div class="nlbl">What they need</div><ul class="nlist">${needs}</ul></div>`:''}<div class="mpills">${pills}</div><div class="cact"><a class="baply" href="${esc(j.url)}" target="_blank" rel="noopener">Apply Now &rarr;</a>${aplBtn}<button class="brch" id="r${i}" onclick="tog(${i})">Reach Out &darr;</button></div></div><div class="outreach" id="o${i}"><div class="oin"><div><div class="olbl">Who to reach out to</div><div class="plinks">${people}</div></div><div><div class="olbl">Connection Request <span style="font-weight:400;font-size:10px;color:#475569">(&lt;300 chars)</span></div><div class="tbox"><button class="cpb" onclick="cp('${cid}',this)">Copy</button><span id="${cid}">${esc(j.conn)}</span></div></div><div><div class="olbl">LinkedIn InMail</div><div class="tbox"><button class="cpb" onclick="cp('${mid}',this)">Copy</button><div id="${mid}">${inmail}</div></div></div></div></div></div>`;
  }).join('');
}
render();
updateAppliedCount();
</script>
</body>
</html>"""

        html = (TMPL
            .replace('__JOBS__',  jobs_json)
            .replace('__NOW__',   now_str)
            .replace('__TOTAL__', str(total))
            .replace('__EXC__',   str(n_exc))
            .replace('__STR__',   str(n_str))
            .replace('__COS__',   str(companies))
        )

        _old = (
            '<!DOCTYPE html>\n'
            '<html lang="en">\n'
            '<head>\n'
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<title>Job Dashboard — Prachita Purohit</title>\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">\n'
            '<style>\n'
            ':root{'
            '--blue:#0073b1;--navy:#0a192f;--green:#16a34a;--green-bg:#f0fdf4;'
            '--strong:#2563eb;--strong-bg:#eff6ff;--gold:#b45309;--gold-bg:#fffbeb;'
            '--bg:#f0f4f8;--card:#fff;--border:#e2e8f0;--text:#1e293b;--muted:#64748b;'
            '--radius:12px;--shadow:0 1px 3px rgba(0,0,0,.08),0 4px 16px rgba(0,0,0,.06);'
            '}\n'
            '*{box-sizing:border-box;margin:0;padding:0}\n'
            'body{font-family:"Inter",sans-serif;background:var(--bg);color:var(--text);min-height:100vh}\n'

            
            '.hdr{background:var(--navy);padding:20px 28px;position:sticky;top:0;z-index:100;'
            'box-shadow:0 2px 12px rgba(0,0,0,.3)}\n'
            '.hdr-top{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:14px}\n'
            '.logo{font-size:18px;font-weight:700;color:#fff;white-space:nowrap}'
            '.logo span{color:#38bdf8}\n'
            '.updated{font-size:11px;color:#94a3b8;margin-left:auto;white-space:nowrap}\n'
            '.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center}\n'
            '.search{flex:1;min-width:180px;max-width:280px;padding:8px 12px;border-radius:8px;'
            'border:1px solid #334155;background:#1e293b;color:#fff;font-size:13px;outline:none}'
            '.search::placeholder{color:#64748b}\n'
            '.search:focus{border-color:#38bdf8}\n'
            '.btn-group{display:flex;gap:4px}\n'
            '.btn{padding:6px 14px;border-radius:7px;border:1px solid #334155;background:transparent;'
            'color:#94a3b8;font-size:12px;font-weight:600;cursor:pointer;transition:.15s}\n'
            '.btn:hover{border-color:#38bdf8;color:#38bdf8}\n'
            '.btn.active{background:#0073b1;border-color:#0073b1;color:#fff}\n'

            
            '.stats{display:flex;gap:24px;padding:16px 28px;background:#fff;'
            'border-bottom:1px solid var(--border);flex-wrap:wrap}\n'
            '.stat{display:flex;flex-direction:column;gap:2px}\n'
            '.stat-val{font-size:22px;font-weight:700;color:var(--navy)}\n'
            '.stat-lbl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}\n'
            '.stat-val.green{color:var(--green)}.stat-val.blue{color:var(--strong)}\n'

            
            '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));'
            'gap:20px;padding:24px 28px;max-width:1400px;margin:0 auto}\n'
            '.no-results{grid-column:1/-1;text-align:center;padding:60px 20px;color:var(--muted)}\n'
            '.no-results h3{font-size:18px;margin-bottom:8px}\n'

            
            '.card{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);'
            'border:1px solid var(--border);overflow:hidden;transition:transform .15s,box-shadow .15s;'
            'display:flex;flex-direction:column}\n'
            '.card:hover{transform:translateY(-2px);box-shadow:0 4px 24px rgba(0,0,0,.12)}\n'
            '.card-bar{height:4px}\n'
            '.bar-green{background:linear-gradient(90deg,#16a34a,#4ade80)}\n'
            '.bar-blue{background:linear-gradient(90deg,#2563eb,#60a5fa)}\n'
            '.bar-gold{background:linear-gradient(90deg,#b45309,#fbbf24)}\n'
            '.card-body{padding:16px 18px;flex:1;display:flex;flex-direction:column;gap:10px}\n'

            
            '.score-row{display:flex;align-items:center;justify-content:space-between}\n'
            '.badge{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;'
            'border-radius:20px;font-size:11px;font-weight:700}\n'
            '.badge-green{background:var(--green-bg);color:var(--green)}\n'
            '.badge-blue{background:var(--strong-bg);color:var(--strong)}\n'
            '.badge-gold{background:var(--gold-bg);color:var(--gold)}\n'
            '.score-num{font-size:28px;font-weight:700;line-height:1}\n'
            '.score-num.green{color:var(--green)}.score-num.blue{color:var(--strong)}'
            '.score-num.gold{color:var(--gold)}\n'

            
            '.card-title{font-size:15px;font-weight:700;color:var(--navy);line-height:1.3}\n'
            '.card-title a{color:inherit;text-decoration:none}\n'
            '.card-title a:hover{color:var(--blue)}\n'
            '.card-meta{font-size:12px;color:var(--muted);display:flex;gap:8px;flex-wrap:wrap;align-items:center}\n'
            '.dot{color:#cbd5e1}\n'

            
            '.chips{display:flex;flex-wrap:wrap;gap:5px}\n'
            '.chip{font-size:10px;font-weight:600;padding:3px 9px;border-radius:20px;'
            'background:var(--green-bg);color:var(--green)}\n'
            '.chip::before{content:"✓ "}\n'

            
            '.needs-lbl{font-size:11px;font-weight:700;color:var(--muted);'
            'text-transform:uppercase;letter-spacing:.04em}\n'
            '.needs-list{list-style:none;display:flex;flex-direction:column;gap:3px}\n'
            '.needs-list li{font-size:12px;color:#475569;padding-left:14px;position:relative;line-height:1.5}\n'
            '.needs-list li::before{content:"›";position:absolute;left:0;color:var(--blue);font-weight:700}\n'

            
            '.pills{display:flex;gap:6px;flex-wrap:wrap}\n'
            '.pill{font-size:11px;padding:2px 10px;border-radius:20px;'
            'background:#f1f5f9;color:var(--muted);font-weight:500}\n'
            '.pill.salary{background:#f0fdf4;color:var(--green)}\n'

            
            '.card-actions{display:flex;gap:8px;margin-top:auto;padding-top:4px}\n'
            '.btn-apply{padding:8px 18px;background:var(--blue);color:#fff;border:none;'
            'border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;text-decoration:none;'
            'transition:.15s}\n'
            '.btn-apply:hover{background:#005f94}\n'
            '.btn-reach{padding:8px 14px;background:#f1f5f9;color:var(--navy);border:1px solid var(--border);'
            'border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;transition:.15s}\n'
            '.btn-reach:hover{background:#e2e8f0}\n'
            '.btn-reach.open{background:var(--navy);color:#fff;border-color:var(--navy)}\n'

            
            '.outreach{border-top:1px solid var(--border);padding:14px 18px;'
            'background:#f8faff;display:none;flex-direction:column;gap:12px}\n'
            '.outreach.visible{display:flex}\n'
            '.out-section-lbl{font-size:11px;font-weight:700;color:var(--blue);'
            'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}\n'
            '.people-links{display:flex;flex-direction:column;gap:4px}\n'
            '.people-link{display:flex;align-items:center;gap:8px;text-decoration:none;'
            'font-size:12px;color:var(--text);padding:5px 8px;border-radius:6px;transition:.12s}\n'
            '.people-link:hover{background:#e8f0fe;color:var(--blue)}\n'
            '.people-link .icon{font-size:14px;width:20px;text-align:center}\n'
            '.people-link .arrow{margin-left:auto;color:var(--muted);font-size:11px}\n'
            '.template-box{background:#fff;border:1px solid var(--border);border-radius:8px;'
            'padding:10px 12px;font-size:12px;color:#334155;line-height:1.7;position:relative}\n'
            '.copy-btn{position:absolute;top:8px;right:8px;padding:3px 10px;font-size:10px;'
            'font-weight:600;border:1px solid var(--border);border-radius:5px;background:#fff;'
            'cursor:pointer;color:var(--muted);transition:.12s}\n'
            '.copy-btn:hover{background:var(--blue);color:#fff;border-color:var(--blue)}\n'
            '.copy-btn.copied{background:#16a34a;color:#fff;border-color:#16a34a}\n'

            
            '.footer{text-align:center;padding:24px;font-size:11px;color:var(--muted)}\n'

            '@media(max-width:600px){'
            '.hdr{padding:14px 16px}.grid{padding:16px}.stats{padding:12px 16px;gap:16px}'
            '.stat-val{font-size:18px}}\n'
            '</style>\n'
            '</head>\n'
            '<body>\n'

            '<header class="hdr">\n'
            '<div class="hdr-top">\n'
            '<div class="logo">Will get you a job <span>bitch</span></div>\n'
            '<span class="updated">Updated: ' + now_str + '</span>\n'
            '</div>\n'
            '<div class="controls">\n'
            '<input class="search" id="search" type="text" placeholder="Search role or company…" oninput="render()">\n'
            '<div class="btn-group" id="score-btns">\n'
            '<button class="btn active" onclick="setFilter(\'score\',\'all\',this)">All</button>\n'
            '<button class="btn" onclick="setFilter(\'score\',\'6\',this)">6+</button>\n'
            '<button class="btn" onclick="setFilter(\'score\',\'8\',this)">8+</button>\n'
            '</div>\n'
            '<div class="btn-group" id="role-btns">\n'
            '<button class="btn active" onclick="setFilter(\'role\',\'all\',this)">All Roles</button>\n'
            '<button class="btn" onclick="setFilter(\'role\',\'brand\',this)">Brand</button>\n'
            '<button class="btn" onclick="setFilter(\'role\',\'pmm\',this)">PMM</button>\n'
            '<button class="btn" onclick="setFilter(\'role\',\'gtm\',this)">GTM</button>\n'
            '<button class="btn" onclick="setFilter(\'role\',\'growth\',this)">Growth</button>\n'
            '</div>\n'
            '</div>\n'
            '</header>\n'

            '<div class="stats">\n'
            '<div class="stat"><span class="stat-val">' + str(total) + '</span><span class="stat-lbl">Total Roles</span></div>\n'
            '<div class="stat"><span class="stat-val green">' + str(n_exc) + '</span><span class="stat-lbl">Excellent (8+)</span></div>\n'
            '<div class="stat"><span class="stat-val blue">' + str(n_str) + '</span><span class="stat-lbl">Strong (6-7)</span></div>\n'
            '<div class="stat"><span class="stat-val">' + str(companies) + '</span><span class="stat-lbl">Companies</span></div>\n'
            '</div>\n'

            '<div class="grid" id="grid"></div>\n'
            '<div class="footer">Entry &amp; manager level only &bull; JD-verified (&le;4 yrs exp) &bull; All US &bull; Scored on 11 resume signals &bull; Auto-updates every 2 hrs</div>\n'

            '<script>\n'
            'const JOBS=' + jobs_json + ';\n'
            'let filters={score:"all",role:"all"};\n'
            'function setFilter(k,v,el){\n'
            '  filters[k]=v;\n'
            '  el.closest(".btn-group").querySelectorAll(".btn").forEach(b=>b.classList.remove("active"));\n'
            '  el.classList.add("active");\n'
            '  render();\n'
            '}\n'
            'function scoreClass(s){return s>=8?"green":s>=6?"blue":"gold";}\n'
            'function barClass(s){return s>=8?"bar-green":s>=6?"bar-blue":"bar-gold";}\n'
            'function badgeClass(s){return s>=8?"badge-green":s>=6?"badge-blue":"badge-gold";}\n'
            'function escHtml(t){return(t||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}\n'
            'function roleMatch(title,role){\n'
            '  if(role==="all")return true;\n'
            '  const t=title.toLowerCase();\n'
            '  if(role==="brand")return t.includes("brand");\n'
            '  if(role==="pmm")return t.includes("product marketing");\n'
            '  if(role==="gtm")return t.includes("gtm")||t.includes("go to market");\n'
            '  if(role==="growth")return t.includes("growth")||t.includes("demand");\n'
            '  return true;\n'
            '}\n'
            'function copyText(id,btn){\n'
            '  const el=document.getElementById(id);\n'
            '  navigator.clipboard.writeText(el.innerText).then(()=>{\n'
            '    btn.textContent="Copied!";btn.classList.add("copied");\n'
            '    setTimeout(()=>{btn.textContent="Copy";btn.classList.remove("copied");},2000);\n'
            '  });\n'
            '}\n'
            'function toggleOutreach(idx){\n'
            '  const panel=document.getElementById("out-"+idx);\n'
            '  const btn=document.getElementById("rbtn-"+idx);\n'
            '  const open=panel.classList.toggle("visible");\n'
            '  btn.textContent=open?"Close ✕":"Reach Out ↓";\n'
            '  btn.classList.toggle("open",open);\n'
            '}\n'
            'function render(){\n'
            '  const q=document.getElementById("search").value.toLowerCase();\n'
            '  const filtered=JOBS.filter(j=>{\n'
            '    if(filters.score!=="all"&&j.score<parseInt(filters.score))return false;\n'
            '    if(!roleMatch(j.title,filters.role))return false;\n'
            '    if(q&&!j.title.toLowerCase().includes(q)&&!j.company.toLowerCase().includes(q))return false;\n'
            '    return true;\n'
            '  });\n'
            '  const grid=document.getElementById("grid");\n'
            '  if(!filtered.length){\n'
            '    grid.innerHTML=\'<div class="no-results"><h3>No roles found</h3><p>Try adjusting your filters or search.</p></div>\';\n'
            '    return;\n'
            '  }\n'
            '  grid.innerHTML=filtered.map((j,i)=>{\n'
            '    const sc=scoreClass(j.score),bc=badgeClass(j.score),bar=barClass(j.score);\n'
            '    const chips=(j.skills||[]).map(s=>`<span class="chip">${escHtml(s)}</span>`).join("");\n'
            '    const needs=(j.needs||[]).map(n=>`<li>${escHtml(n)}</li>`).join("");\n'
            '    const pills=`<span class="pill">${escHtml(j.exp||"Exp N/A")}</span>`\n'
            '      +(j.salary?`<span class="pill salary">${escHtml(j.salary)}</span>`:"");\n'
            '    const people=(j.people||[]).map(p=>\n'
            '      `<a class="people-link" href="${escHtml(p.url)}" target="_blank" rel="noopener">`\n'
            '      +`<span class="icon">${p.icon}</span>`\n'
            '      +`<span>${escHtml(p.label)}</span>`\n'
            '      +`<span class="arrow">↗</span></a>`\n'
            '    ).join("");\n'
            '    const connId="conn-"+i,mailId="mail-"+i;\n'
            '    const inmail=(j.inmail||[]).map(l=>`<p>${escHtml(l)}</p>`).join("");\n'
            '    return `<div class="card">`\n'
            '      +`<div class="card-bar ${bar}"></div>`\n'
            '      +`<div class="card-body">`\n'
            '      +`<div class="score-row">`\n'
            '      +`<div class="score-num ${sc}">${j.score}<span style="font-size:14px;font-weight:500;color:#94a3b8">/10</span></div>`\n'
            '      +`<span class="badge ${bc}">${escHtml(j.label)}</span>`\n'
            '      +`</div>`\n'
            '      +`<div>`\n'
            '      +`<div class="card-title"><a href="${escHtml(j.url)}" target="_blank" rel="noopener">${escHtml(j.title)}</a></div>`\n'
            '      +`<div class="card-meta"><span>${escHtml(j.company)}</span><span class="dot">•</span><span>${escHtml(j.location)}</span><span class="dot">•</span><span>${escHtml(j.date)}</span></div>`\n'
            '      +`</div>`\n'
            '      +(chips?`<div class="chips">${chips}</div>`:"") \n'
            '      +(needs?`<div><div class="needs-lbl">What they need</div><ul class="needs-list">${needs}</ul></div>`:"") \n'
            '      +`<div class="pills">${pills}</div>`\n'
            '      +`<div class="card-actions">`\n'
            '      +`<a class="btn-apply" href="${escHtml(j.url)}" target="_blank" rel="noopener">Apply Now →</a>`\n'
            '      +`<button class="btn-reach" id="rbtn-${i}" onclick="toggleOutreach(${i})">Reach Out ↓</button>`\n'
            '      +`</div>`\n'
            '      +`</div>`\n'
            '      +`<div class="outreach" id="out-${i}">`\n'
            '      +`<div><div class="out-section-lbl">Who to reach out to</div><div class="people-links">${people}</div></div>`\n'
            '      +`<div><div class="out-section-lbl">Connection Request <span style="font-weight:400;text-transform:none;font-size:10px;color:#94a3b8">(&lt;300 chars)</span></div>`\n'
            '      +`<div class="template-box" style="padding-right:72px"><button class="copy-btn" onclick="copyText(\'${connId}\',this)">Copy</button><span id="${connId}">${escHtml(j.conn)}</span></div></div>`\n'
            '      +`<div><div class="out-section-lbl">LinkedIn InMail</div>`\n'
            '      +`<div class="template-box" style="padding-right:72px"><button class="copy-btn" onclick="copyText(\'${mailId}\',this)">Copy</button><div id="${mailId}">${inmail}</div></div></div>`\n'
            '      +`</div>`\n'
            '      +`</div>`;\n'
            '  }).join("");\n'
            '}\n'
            'render();\n'
            '</script>\n'
            '</body>\n'
            '</html>\n'
        )

        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Generated index.html — " + str(total) + " jobs")

        _old  # noqa: suppress unused warning

    # ── Main ──────────────────────────────────────────────────────────

    def run(self):
        print("=" * 60)
        print("LinkedIn PMM / Brand / GTM Job Scraper")
        print("Entry/Manager Level | All US | Resume-Matched")
        print("=" * 60)

        existing = self.load_existing_jobs()
        print("Loaded " + str(len(existing)) + " existing jobs")

        current  = self.scrape_jobs()
        new_jobs = self.find_new_jobs(current, existing)
        print("Detected " + str(len(new_jobs)) + " new jobs — fetching JDs (max 40)...")

        new_jobs = self.enrich_with_jd(new_jobs)

        for job in new_jobs:
            existing[job['id']] = job
        self.save_jobs(existing)
        print("Database: " + str(len(existing)) + " total jobs")

        self.generate_html(existing)

        if new_jobs:
            self.send_email_notification(new_jobs)
            print("\nSummary (score > 5):")
            for job in sorted([j for j in new_jobs if j.get('relevance_score',0) > 5],
                              key=lambda j: j['relevance_score'], reverse=True):
                print("  [" + str(job['relevance_score']) + "/10] " +
                      self.clean_text(job['title']) + " @ " + self.clean_text(job['company']))
        else:
            print("No new jobs after filtering.")
        print("=" * 60)


if __name__ == "__main__":
    LinkedInJobScraper().run()
