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
            'senior director', 'sr. director', 'sr director',
            'vice president', 'vp ', ' vp,', '(vp)', 'svp', 'evp',
            'head of', 'chief ', 'cmo', 'ceo', 'coo',
            'principal ', 'group director', 'global director',
            'director of', 'director,',
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
        return any(kw in title.lower() for kw in self.senior_title_keywords)

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

    def _role_area(self, title):
        t = title.lower()
        if 'brand' in t:        return 'brand marketing manager', 'brand director marketing'
        if 'product marketing'  in t: return 'product marketing manager', 'marketing director'
        if 'integrated' in t:   return 'integrated marketing manager', 'vp marketing'
        if 'gtm' in t or 'go to market' in t: return 'go to market manager', 'marketing director'
        return 'marketing manager', 'marketing director'

    def people_search_links(self, company, title):
        peer_role, mgr_role = self._role_area(title)
        def url(q):
            return 'https://www.linkedin.com/search/results/people/?keywords=' + urllib.parse.quote(q) + '&origin=GLOBAL_SEARCH_HEADER'
        return [
            ('People in Similar Roles',    url(peer_role + ' ' + company)),
            ('Potential Hiring Managers',  url(mgr_role  + ' ' + company)),
            ('HR / Recruiters',            url('recruiter talent acquisition ' + company)),
        ]

    def connection_request(self, company, title, matched):
        skill = next((s for s in matched
                      if s not in ('MBA preferred/required', 'Strong title alignment')), 'brand and GTM marketing')
        msg = ('Hi [Name], I\'m a Babson MBA with experience in ' + skill.lower() +
               ' and noticed ' + company + ' is hiring for ' + title +
               '. Would love to connect and learn about your experience on the team!')
        return msg[:295]   # LinkedIn connection request limit

    def inmail_template(self, company, title, matched):
        skills = [s for s in matched if s not in ('MBA preferred/required', 'Strong title alignment')]
        skills_str = ' and '.join(skills[:2]) if skills else 'brand strategy and go-to-market execution'
        return [
            'Hi [Name],',
            'I came across the ' + title + ' role at ' + company +
            ' and was immediately excited — it aligns closely with my background in ' + skills_str + '.',
            'I\'m a Babson MBA (Marketing & Entrepreneurship, May 2026) with hands-on experience in '
            'GTM strategy, consumer insights research, and B2B marketing. Recently I built a full '
            'segmentation-to-launch GTM strategy for a Gates Foundation project and conducted '
            'consumer research across 52 families for a nonprofit board.',
            'I\'d love to hear what success looks like in this role and learn more about the team. '
            'Would you be open to a quick 15-minute chat? Completely no pressure.',
            'Thank you, Prachita',
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

            # ── Job details card ──────────────────────────────────────
            bp.append('<div style="margin:12px 28px 0;border:1px solid #e0e0e0;border-left:4px solid '
                      + accent + ';border-radius:0 6px 0 0;background:#fff;padding:14px 16px;">')

            # Title row
            bp.append('<table width="100%" style="margin-bottom:6px;"><tr>'
                      '<td style="vertical-align:top;">'
                      '<span style="font-size:14px;font-weight:700;color:#0073b1;">' + str(idx) + '. ' + title + '</span><br>'
                      '<span style="font-size:12px;color:#555;">' + company + ' &bull; '
                      + self.clean_text(job.get('location','')) + '</span></td>'
                      '<td align="right" style="vertical-align:top;white-space:nowrap;">'
                      '<span style="background:' + lb + ';color:' + lc + ';font-size:11px;font-weight:700;'
                      'padding:3px 10px;border-radius:10px;">' + ml + ' &bull; ' + str(sc) + '/10</span>'
                      '</td></tr></table>')

            # Meta pills
            bp.append('<p style="margin:4px 0;">'
                      '<span style="background:#f1f3f4;color:#444;font-size:11px;padding:2px 8px;border-radius:10px;margin-right:6px;">'
                      'Exp: ' + self.clean_text(job.get('years_required','Not specified')) + '</span>')
            if salary:
                bp.append('<span style="background:#f1f3f4;color:#444;font-size:11px;padding:2px 8px;border-radius:10px;">'
                          + salary + '</span>')
            bp.append('</p>')

            # Matched skills as green chips
            display_matched = [s for s in matched if s not in ('MBA preferred/required', 'Strong title alignment')]
            if display_matched:
                bp.append('<p style="margin:8px 0 3px;font-size:12px;color:#555;font-weight:600;">Your skills this role values:</p>'
                          '<p style="margin:2px 0;">')
                for s in display_matched:
                    bp.append('<span style="display:inline-block;background:#e6f4ea;color:#137333;font-size:11px;'
                              'font-weight:600;padding:2px 8px;border-radius:10px;margin:2px 4px 2px 0;">'
                              '&#10003; ' + self.clean_text(s) + '</span>')
                bp.append('</p>')

            # Key JD requirements
            if skills:
                bp.append('<p style="margin:8px 0 3px;font-size:12px;color:#555;font-weight:600;">What they\'re looking for:</p>'
                          '<ul style="margin:2px 0;padding-left:16px;font-size:12px;color:#444;line-height:1.6;">')
                for s in skills:
                    bp.append('<li>' + self.clean_text(s) + '</li>')
                bp.append('</ul>')

            # Apply button
            bp.append('<div style="margin-top:12px;">'
                      '<a href="' + url + '" style="display:inline-block;background:#0073b1;color:#fff;'
                      'font-size:12px;font-weight:700;padding:7px 16px;border-radius:4px;text-decoration:none;">Apply Now &rarr;</a>'
                      '<span style="font-size:11px;color:#aaa;margin-left:12px;">Found: '
                      + str(job.get('found_date',''))[:10] + '</span></div>')
            bp.append('</div>')   # end job card

            # ── Outreach section (attached below job card) ────────────
            links   = self.people_search_links(company, title)
            conn    = self.connection_request(company, title, matched)
            inmail  = self.inmail_template(company, title, matched)

            bp.append('<div style="margin:0 28px 16px;border:1px solid #e0e0e0;border-top:none;'
                      'border-radius:0 0 6px 6px;background:#f8faff;padding:14px 16px;">')

            # Who to reach out to
            bp.append('<p style="margin:0 0 8px;font-size:12px;font-weight:700;color:#0073b1;">Who to reach out to at ' + company + '</p>'
                      '<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;">')
            icons = ['&#128101;', '&#128084;', '&#128203;']
            for (lbl, href), icon in zip(links, icons):
                bp.append('<tr><td style="padding:3px 0;font-size:12px;color:#555;width:200px;">'
                          + icon + ' ' + lbl + '</td>'
                          '<td style="padding:3px 0;"><a href="' + href + '" style="font-size:12px;color:#0073b1;'
                          'text-decoration:none;font-weight:600;">Search on LinkedIn &rarr;</a></td></tr>')
            bp.append('</table>')

            # Connection request
            bp.append('<p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#333;">'
                      'Connection Request <span style="font-weight:400;color:#888;">(copy-paste, &lt;300 chars)</span></p>'
                      '<div style="background:#fff;border:1px solid #dde3f0;border-radius:4px;padding:10px 12px;'
                      'font-size:12px;color:#333;line-height:1.6;margin-bottom:10px;">'
                      + self.clean_text(conn) + '</div>')

            # InMail
            bp.append('<p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#333;">'
                      'LinkedIn InMail <span style="font-weight:400;color:#888;">(for hiring managers)</span></p>'
                      '<div style="background:#fff;border:1px solid #dde3f0;border-radius:4px;padding:10px 12px;">')
            for line in inmail:
                bp.append('<p style="margin:4px 0;font-size:12px;color:#333;line-height:1.6;">'
                          + self.clean_text(line) + '</p>')
            bp.append('</div></div>')   # end outreach section

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
