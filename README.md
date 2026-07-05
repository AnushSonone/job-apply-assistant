# job-apply-assistant

Monitors [SimplifyJobs off-season internships](https://github.com/SimplifyJobs/Summer2026-Internships/blob/dev/README-Off-Season.md), sends Telegram alerts with tailored resumes, and autofill job applications from a local answer bank.

## Architecture

| Phase | Where | What |
|-------|-------|------|
| **1 — Scanner** | GitHub Actions (every 5 min) | Detect new/reopened jobs → tailor resume → Telegram |
| **2 — Apply** | Your Mac | Brave CDP autofill from answer bank → you review & submit |

## Quick start (local)

```bash
cd ~/Desktop/anushprojects/job-apply-assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
python -m job_assistant setup
python -m job_assistant import-resume
# Edit job_assistant/data/profile.json
```

## GitHub setup (public repo)

1. Push to `git@github.com:AnushSonone/job-apply-assistant.git`
2. Add **Secrets** (Settings → Secrets → Actions):
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `ANTHROPIC_API_KEY`
   - `MASTER_RESUME` — paste `cat job_assistant/data/master_resume.md`
   - `PROFILE_JSON` — paste `cat job_assistant/data/profile.json`
3. Add **Variable**: `UPSTREAM_README_SHA` (leave empty; CI sets it)
4. Commit `job_assistant/data/scanner.db` (`python -m job_assistant init-db`)

## Commands

```bash
python -m job_assistant init-db
python -m job_assistant import-resume
python -m job_assistant scan
python -m job_assistant list --active
python -m job_assistant autofill --job-id ID --advance
python -m job_assistant add-answer "how did you hear" "LinkedIn"
python -m job_assistant log-apply ID
```

## Resume revision (after Telegram alert)

Claude can revise the tailored resume based on your feedback. Same guardrails as initial tailor (no invented facts).

**Option A — Reply on Telegram** (laptop running bot):
```bash
python -m job_assistant telegram-bot   # leave running
# Reply to the resume file: "Shorten the Visa bullet, less buzzwords"
```

**Option B — One-shot CLI:**
```bash
python -m job_assistant revise-resume --job-id abc123 "Don't say agentic in the Visa bullet" --telegram
```

**Option C — Interactive terminal chat:**
```bash
python -m job_assistant revise-chat --job-id abc123
```

Each revision calls Claude once (~3–6k tokens). History is stored in `local.db` for multi-turn feedback.


1. Telegram: job alert + tailored resume + change summary
2. Review resume on phone
3. Brave with CDP → open apply link
4. `python -m job_assistant autofill --job-id <id> --advance`
5. Fill unmatched questions → submit manually
6. `python -m job_assistant log-apply <id>`

```bash
open -a "Brave Browser" --args --remote-debugging-port=9222
```
