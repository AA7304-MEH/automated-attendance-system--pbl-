"""Email digest delivery (Phase 5).

Two backends:
    "console" (default) — renders the digest to data/outputs/emails/ so the
    demo works with zero credentials; the preview page shows the exact email.
    "smtp" — real delivery via SMTP_HOST/SMTP_USER/SMTP_PASSWORD env vars.

`scripts/send_alerts.py` calls send_digest() from a cron job in production.
"""

import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from flask import render_template

from config import (
    ATTENDANCE_THRESHOLD, EMAIL_BACKEND, EMAILS_DIR, SMTP_FROM, SMTP_HOST,
    SMTP_PASSWORD, SMTP_PORT, SMTP_USER,
)
from reports import split_risk, student_summary


def build_digest():
    """Build the digest. Returns (subject, text_body, html_body)."""
    summary = student_summary()
    at_risk, borderline = split_risk(summary)
    subject = (
        f"[AutoAttendance] {len(at_risk)} student(s) below "
        f"{ATTENDANCE_THRESHOLD:.0f}% attendance"
    )
    html = render_template(
        "email_digest.html",
        at_risk=at_risk, borderline=borderline, threshold=ATTENDANCE_THRESHOLD,
        generated=datetime.now().strftime("%d %b %Y, %H:%M"),
    )
    lines = [
        subject,
        "",
        "AT-RISK STUDENTS (< %.0f%%)" % ATTENDANCE_THRESHOLD,
    ]
    for s in at_risk:
        lines.append(
            f"  {s['student'].student_id}  {s['student'].full_name:<20} "
            f"{s['pct']:5.1f}%  last7d {s['recent_pct']:5.1f}%  {s['worst_subject'] or ''}"
        )
    if borderline:
        lines.append("")
        lines.append("BORDERLINE (watch list)")
        for s in borderline:
            lines.append(
                f"  {s['student'].student_id}  {s['student'].full_name:<20} "
                f"{s['pct']:5.1f}%"
            )
    return subject, "\n".join(lines), html


def send_digest(recipients):
    """Send the digest to `recipients` (list of emails).

    Returns a human-readable status string. Console backend writes the
    rendered email to data/outputs/emails/ instead of transmitting.
    """
    if not recipients:
        return "no-recipients"
    subject, text, html = build_digest()

    if EMAIL_BACKEND != "smtp" or not SMTP_HOST:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = EMAILS_DIR / f"digest_{ts}"
        base.with_suffix(".html").write_text(html)
        base.with_suffix(".txt").write_text(
            f"To: {', '.join(recipients)}\nSubject: {subject}\n\n{text}"
        )
        print(f"[mailer:console] digest written -> {base.with_suffix('.html')}")
        return f"console:{base.with_suffix('.html')}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = ", ".join(recipients)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls(context=context)
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    return "smtp:ok"
