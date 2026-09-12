#!/usr/bin/env python3
"""Send the low-attendance digest (cron-friendly).

    python scripts/send_alerts.py --preview    # print the text digest, send nothing
    python scripts/send_alerts.py              # send to all teachers (or ALERT_RECIPIENTS)

Production:  0 8 * * *  cd /path/to/attendance-system && python scripts/send_alerts.py
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import ALERT_RECIPIENTS, EMAIL_BACKEND, SMTP_HOST


def main():
    ap = argparse.ArgumentParser(description="Low-attendance email digest")
    ap.add_argument("--preview", action="store_true", help="print digest, send nothing")
    args = ap.parse_args()

    from app import app  # needs the app context for templates + DB
    from database.models import Teacher
    from mailer import build_digest, send_digest

    with app.app_context():
        if args.preview:
            subject, text, _html = build_digest()
            print(f"Subject: {subject}\n\n{text}")
            return

        recipients = ALERT_RECIPIENTS or [
            t.email for t in Teacher.query.all() if t.email
        ]
        status = send_digest(recipients)
        if status.startswith("console"):
            print("Email backend is 'console' (set EMAIL_BACKEND=smtp + SMTP_* to "
                  "actually send). Digest saved under data/outputs/emails/.")
        elif status == "smtp:ok":
            print(f"Digest sent to {len(recipients)} recipient(s) via {SMTP_HOST}.")
        else:
            print(f"Nothing sent: {status}")


if __name__ == "__main__":
    main()
