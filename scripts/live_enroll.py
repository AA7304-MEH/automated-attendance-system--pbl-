#!/usr/bin/env python3
"""Enroll a dataset folder into a RUNNING instance over HTTP (no shell needed).

Works against localhost or the live Render URL. Logs in as a staff user,
then POSTs each <ROLL>_<First>_<Last>.jpg portrait to /students exactly like
the web form does (CSRF + multipart), so DB row + portrait + face encoding
are created server-side.

Usage:
    python scripts/live_enroll.py https://autoattendance-xjeg.onrender.com /path/to/dataset
    python scripts/live_enroll.py http://localhost:8000 data/dataset --email teacher@college.edu
"""

import argparse
import re
import sys
import time
from pathlib import Path

import requests

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def parse_name(path):
    stem = path.stem.replace("-", "_").replace(" ", "_")
    parts = [p for p in stem.split("_") if p]
    roll = parts[0].upper()
    first = parts[1] if len(parts) > 1 else "Student"
    last = " ".join(parts[2:]) if len(parts) > 2 else roll
    return roll, first, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url")
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--email", default="teacher@college.edu")
    ap.add_argument("--password", default="teacher123")
    ap.add_argument("--pin", default="1234")
    ap.add_argument("--department", default=None)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    files = sorted(p for p in args.dataset.glob("*.jpg"))
    files += sorted(p for p in args.dataset.glob("*.jpeg"))
    files += sorted(p for p in args.dataset.glob("*.png"))
    if not files:
        sys.exit(f"no portraits found in {args.dataset}")

    s = requests.Session()
    s.headers["User-Agent"] = "live-enroll/1.0"

    print(f"target : {base}")
    r = s.get(f"{base}/login", timeout=180)
    r.raise_for_status()
    tok = CSRF_RE.search(r.text).group(1)
    r = s.post(f"{base}/login", data={"csrf_token": tok, "email": args.email,
                                      "password": args.password}, timeout=180)
    if "/logout" not in r.text and "dashboard" not in r.url:
        sys.exit("login failed — check credentials")
    print(f"login  : OK as {args.email}")

    # existing roster (skip duplicates)
    r = s.get(f"{base}/export/students.csv", timeout=180)
    existing = set()
    for line in r.text.splitlines()[1:]:
        if line.strip():
            existing.add(line.split(",")[0].strip().upper())
    print(f"roster : {len(existing)} student(s) already enrolled")

    ok = skip = fail = 0
    for p in files:
        roll, first, last = parse_name(p)
        if roll in existing:
            print(f"  [skip] {roll} {first} {last} (already enrolled)")
            skip += 1
            continue
        tok = CSRF_RE.search(s.get(f"{base}/students", timeout=180).text).group(1)
        data = {
            "csrf_token": tok,
            "student_id": roll,
            "first_name": first,
            "last_name": last,
            "email": "",
            "department": args.department or "",
            "semester": "",
            "portal_pin": args.pin,
        }
        with open(p, "rb") as fh:
            r = s.post(f"{base}/students", data=data,
                       files={"photo": (p.name, fh, "image/jpeg")},
                       timeout=300, allow_redirects=True)
        if "Enrolled" in r.text and roll in r.text:
            print(f"  [ok  ] {roll} {first} {last}")
            ok += 1
        else:
            print(f"  [FAIL] {roll} {first} {last} (HTTP {r.status_code})")
            fail += 1
        time.sleep(0.5)

    print(f"\ndone: {ok} enrolled, {skip} skipped, {fail} failed")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
