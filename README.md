# LinkedIn Investment Banking Job Scraper 🚀

Automatically scrapes LinkedIn for new investment banking jobs in the United States and sends you email notifications **every 15 minutes** - completely FREE using GitHub Actions!

## 🎯 Features

- ✅ Runs automatically every 15 minutes (24/7)
- ✅ Monitors investment banking jobs across United States
- ✅ Email notifications for new postings only
- ✅ 100% Free (no credit card required)
- ✅ No server maintenance needed
- ✅ Tracks job history to avoid duplicate alerts

## 📋 Prerequisites

- GitHub account (free)
- Gmail account (for sending notifications)

## 🚀 Setup Instructions

### Step 1: Enable Gmail App Password

Since you'll be using Gmail to send notifications, you need to create an "App Password":

1. Go to your Google Account: https://myaccount.google.com/
2. Click on **Security** (left sidebar)
3. Enable **2-Step Verification** if not already enabled
4. Once 2FA is enabled, go back to Security
5. Search for "App passwords" or scroll down to find it
6. Click **App passwords**
7. Select **Mail** and **Other (Custom name)**
8. Name it "LinkedIn Job Scraper"
9. Click **Generate**
10. **Copy the 16-character password** (you'll need this in Step 3)

### Step 2: Fork This Repository

1. Click the **Fork** button at the top right of this page
2. This creates your own copy of the project

### Step 3: Add GitHub Secrets

You need to add your email credentials as GitHub Secrets (they're encrypted and safe):

1. Go to your forked repository
2. Click **Settings** tab
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Add these three secrets one by one:

   **Secret 1:**
   - Name: `SENDER_EMAIL`
   - Value: Your Gmail address (e.g., `yourname@gmail.com`)

   **Secret 2:**
   - Name: `SENDER_PASSWORD`
   - Value: The 16-character App Password from Step 1

   **Secret 3:**
   - Name: `RECIPIENT_EMAIL`
   - Value: Email where you want to receive notifications (can be same as sender)

### Step 4: Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. Click **"I understand my workflows, go ahead and enable them"**
3. The scraper will now run automatically every 15 minutes!

### Step 5: Test It Manually (Optional)

Want to test immediately without waiting 15 minutes?

1. Go to **Actions** tab
2. Click on **LinkedIn Job Scraper** workflow (left sidebar)
3. Click **Run workflow** button (right side)
4. Click the green **Run workflow** button
5. Watch it run in real-time!

## 📧 What You'll Receive

When new investment banking jobs are posted, you'll get an email like this:

```
Subject: 🚨 3 New Investment Banking Job(s) Found!

New Investment Banking Jobs in United States

─────────────────────────────────
Investment Banking Analyst
Company: Goldman Sachs
Location: New York, NY
[View Job Posting]
Found: 2024-01-20 14:30:00
─────────────────────────────────
```

## ⚙️ Customization

### Change Job Search Keywords

Edit `scraper.py` line 36:

```python
'keywords': 'investment banking',  # Change to 'private equity', 'M&A', etc.
```

### Change Location

Edit `scraper.py` line 37:

```python
'location': 'United States',  # Change to 'New York, NY', 'California', etc.
```

### Change Check Frequency

Edit `.github/workflows/scraper.yml` line 6:

```yaml
- cron: '*/15 * * * *'  # Every 15 minutes
# Options:
# '*/30 * * * *'  # Every 30 minutes
# '0 * * * *'     # Every hour
# '0 */2 * * *'   # Every 2 hours
```

**Note:** GitHub Actions minimum is 5 minutes, but 15 minutes is recommended to stay within free tier limits.

## 📊 How It Works

1. **GitHub Actions** runs the Python script every 15 minutes
2. **Scraper** checks LinkedIn for new investment banking jobs
3. **Database** (`jobs_database.json`) tracks previously seen jobs
4. **Comparison** identifies genuinely new postings
5. **Email** sends you notifications only for new jobs
6. **Repeat** automatically every 15 minutes

## 🔒 Privacy & Security

- Your email credentials are stored as encrypted GitHub Secrets
- The scraper only reads public job postings
- No personal data is collected or stored
- The jobs database is stored in your private repository

## 🆓 Cost Breakdown

- **GitHub Actions**: Free (2,000 minutes/month on free plan)
- **This scraper uses**: ~30 seconds per run = ~720 minutes/month
- **Your cost**: $0.00 forever ✨

## 🛠️ Troubleshooting

### Not receiving emails?

1. Check your spam folder
2. Verify GitHub Secrets are set correctly (Settings → Secrets)
3. Check Actions tab for error logs
4. Make sure Gmail App Password is correct (not your regular password)

### Scraper not running?

1. Make sure GitHub Actions is enabled (Actions tab)
2. Check if workflow file is in `.github/workflows/` folder
3. Look for errors in Actions tab → Latest run

### Want to stop notifications?

1. Go to Actions tab
2. Click LinkedIn Job Scraper (left sidebar)
3. Click the ⋯ menu (top right)
4. Select "Disable workflow"

## 📝 Notes

- LinkedIn may update their HTML structure, which could break the scraper
- The scraper respects LinkedIn's rate limits with random delays
- First run will treat all current jobs as "new" - you'll get a batch email
- After first run, you'll only get emails for genuinely new postings

## 🤝 Contributing

Found a bug? Have an improvement? Feel free to:
- Open an Issue
- Submit a Pull Request
- Fork and modify for your needs

## ⚖️ Legal Notice

This tool is for educational purposes. Please:
- Use responsibly and respect LinkedIn's Terms of Service
- Don't spam or abuse the service
- Add reasonable delays between requests (already built-in)
- Consider using official APIs for commercial use

## 📞 Support

If you run into issues:
1. Check the Troubleshooting section above
2. Review the Actions logs for error messages
3. Open an Issue on GitHub

---

**Happy job hunting! 🎯 Good luck with your investment banking career!**

Made with ❤️ for students on a budget
