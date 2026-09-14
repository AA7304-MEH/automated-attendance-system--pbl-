# 🚀 Deployment Guide

Four options, cheapest first. All use the same codebase; the only required
external config is optional SMTP for emails.

---

## Option A — Docker on any server / VM (recommended)

Works on any host with Docker (DigitalOcean droplet, AWS EC2, GCP, college lab server):

```bash
git clone https://github.com/AA7304-MEH/automated-attendance-system--pbl-.git
cd automated-attendance-system--pbl-
docker compose up -d          # builds + runs on port 8000, data/ persisted
curl http://SERVER_IP:8000/login
```

Behind a domain + HTTPS (production), put a reverse proxy in front, e.g.
Caddy (auto-HTTPS): `attendance.yourcollege.edu { reverse_proxy localhost:8000 }`

## Option B — Render.com (free tier, ~5 minutes, no server)

1. Repo is on GitHub (done).
2. render.com → **New → Web Service** → connect the repo.
3. Settings: **Environment: Docker** (auto-detected from the Dockerfile) ·
   Instance: Free · **Disk** (important): mount `/app/data`, 1 GB, so the
   SQLite DB and encodings persist across deploys.
4. Deploy. First boot auto-seeds demo data and builds `face_encodings.pkl`.
5. Change the seeded passwords before showing it publicly.

## Option C — Railway.com (free tier)

1. railway.app → **New Project → Deploy from GitHub repo** → select the repo.
2. Add a **Volume** mounted at `/app/data`.
3. Railway assigns a public URL automatically.

## Option D — Plain Python (college lab / laptop)

```bash
bash scripts/setup_env.sh     # or: pip install -r requirements.txt (needs dlib)
python app.py                 # dev server on 0.0.0.0:8000

# production-grade (what runs in the demo preview):
pip install gunicorn
gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 180 app:app
```

---

## Environment variables (optional)

| Variable | Default | Purpose |
|---|---|---|
| `EMAIL_BACKEND` | `console` | `smtp` = real email delivery |
| `SMTP_HOST` / `SMTP_PORT` | — / 587 | e.g. `smtp.gmail.com` / 587 (use an App Password) |
| `SMTP_USER` / `SMTP_PASSWORD` | — | SMTP login |
| `SMTP_FROM` | `autoattendance@college.edu` | From header |
| `ALERT_RECIPIENTS` | all teachers | comma-separated override |

Cron for the daily digest (server):

```
0 8 * * *  cd /path/to/attendance-system && python scripts/send_alerts.py
```

## Post-deploy checklist

- [ ] `/login` loads over HTTPS
- [ ] Change seeded passwords: admin, arjun, and the student PIN `1234`
- [ ] Enroll real students (Students → Enroll) — portraits stay in the `data/`
      volume, **never in git**
- [ ] Set `EMAIL_BACKEND=smtp` + SMTP vars for real digests
- [ ] `/alerts → Preview email` renders correctly
