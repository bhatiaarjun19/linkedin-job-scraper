# Quick Setup Checklist ✅

Follow these steps in order:

## 1️⃣ Get Gmail App Password
- [ ] Go to https://myaccount.google.com/security
- [ ] Enable 2-Step Verification
- [ ] Create App Password for "Mail"
- [ ] Copy the 16-character password (save it somewhere temporarily)

## 2️⃣ Test Locally (Optional but Recommended)
- [ ] Download this repository
- [ ] Run: `python test_email.py`
- [ ] Verify you receive the test email
- [ ] If it works, proceed to Step 3

## 3️⃣ Fork Repository
- [ ] Click "Fork" button on GitHub
- [ ] Wait for fork to complete

## 4️⃣ Add GitHub Secrets
Go to: Settings → Secrets and variables → Actions → New repository secret

- [ ] Add `SENDER_EMAIL` = your Gmail address
- [ ] Add `SENDER_PASSWORD` = your 16-character App Password
- [ ] Add `RECIPIENT_EMAIL` = email where you want notifications

## 5️⃣ Enable GitHub Actions
- [ ] Go to Actions tab
- [ ] Click "I understand my workflows, go ahead and enable them"

## 6️⃣ Test Run (Optional)
- [ ] Actions tab → LinkedIn Job Scraper → Run workflow
- [ ] Watch it run
- [ ] Check your email for results

## 7️⃣ Customize (Optional)
- [ ] Edit search keywords in `scraper.py`
- [ ] Change location filter
- [ ] Adjust check frequency in `.github/workflows/scraper.yml`

## ✅ Done!

You'll now receive email alerts for new investment banking jobs every 15 minutes!

---

### Troubleshooting

**No emails?**
- Check spam folder
- Verify GitHub Secrets are correct
- Check Actions tab for errors

**Want to stop?**
- Actions → LinkedIn Job Scraper → ⋯ → Disable workflow

**Questions?**
- Read the full README.md
- Check GitHub Actions logs
- Open an Issue
