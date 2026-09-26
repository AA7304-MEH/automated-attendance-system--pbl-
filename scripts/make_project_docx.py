#!/usr/bin/env python3
"""Generate docs/AutoAttendance_Project_Report.docx — the complete, editable
Word report: cover, all features, tech stack, architecture, database, routes,
measured results, viva Q&A. Regenerate anytime: python scripts/make_project_docx.py
"""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "AutoAttendance_Project_Report.docx"

NAVY = RGBColor(0x14, 0x1A, 0x2E)
ACCENT = RGBColor(0x43, 0x61, 0xEE)
PURPLE = RGBColor(0x72, 0x09, 0xB7)
GRAY = RGBColor(0x6B, 0x74, 0x90)
INK = RGBColor(0x23, 0x2A, 0x42)

doc = Document()

# base styles
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(10.5)
st.font.color.rgb = INK
for lvl, sz, col in (("Heading 1", 17, NAVY), ("Heading 2", 13.5, PURPLE), ("Heading 3", 11.5, ACCENT)):
    s = doc.styles[lvl]
    s.font.name = "Calibri"
    s.font.size = Pt(sz)
    s.font.bold = True
    s.font.color.rgb = col


def para(text="", size=10.5, bold=False, color=None, align=None, style=None, space_after=6):
    p = doc.add_paragraph(style=style)
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    if color:
        r.font.color.rgb = color
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(space_after)
    return p


def bullets(items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        r = p.add_run(it)
        r.font.size = Pt(10.5)
        p.paragraph_format.space_after = Pt(2)


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.makeelement(qn("w:shd"), {qn("w:val"): "clear", qn("w:fill"): hex_color})
    tcPr.append(shd)


def table(headers, rows, widths=None, header_fill="141A2E"):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        r = hdr[i].paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(hdr[i], header_fill)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(9.5)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def code_block(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.name = "Consolas"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
    r.font.size = Pt(8.5)
    r.font.color.rgb = RGBColor(0x2D, 0x34, 0x50)
    p.paragraph_format.space_after = Pt(8)


def callout(text, fill="EEF1FD"):
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]
    c.text = ""
    r = c.paragraphs[0].add_run(text)
    r.font.size = Pt(10)
    r.italic = False
    shade(c, fill)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


# ═══════════════ COVER ═══════════════
para("AUTOMATED STUDENT ATTENDANCE SYSTEM", 26, True, NAVY, "center", space_after=2)
para("AI-Suggested, Teacher-Verified Attendance from Classroom Photos", 13, False, PURPLE, "center")
para("Human-in-the-Loop AI — Complete Project Report", 11.5, False, GRAY, "center", space_after=18)
para("🎓", 40, False, None, "center", space_after=12)

table(["Field", "Details"], [
    ["Project", "Automated Student Attendance System (PBL)"],
    ["Live deployment", "https://autoattendance-xjeg.onrender.com (Render · Docker · HTTPS)"],
    ["Source code", "github.com/AA7304-MEH/automated-attendance-system--pbl-"],
    ["Tech stack (one line)", "Python · Flask · SQLAlchemy (SQLite/Postgres) · dlib face_recognition · OpenCV · Pillow · pandas · Gunicorn · Docker"],
    ["Quality evidence", "61 automated checks passing (11 engine + 50 web) + 20/20 live deployment checks"],
    ["Demo logins", "Admin: teacher@college.edu / teacher123 · Teacher: arjun@college.edu / teacher123 · Student portal: roll no + PIN 1234"],
    ["Core idea", "One classroom photo → every face detected & matched → AI pre-fills attendance → teacher confirms / corrects / assigns → auditable register"],
    ["Submitted by", "Aditya Mehra"],
], widths=[1.6, 5.2])

doc.add_paragraph()
para("CONTENTS", 12, True, NAVY)
toc = ("1. Executive Summary   ·   2. Problem & Objectives   ·   3. System Architecture   ·   4. Technology Stack   ·   "
       "5. Face-Recognition Engine (deep dive)   ·   6. Complete Feature Walkthrough   ·   7. Database Design   ·   "
       "8. Route Map   ·   9. Project Structure   ·   10. Testing & Results   ·   11. How to Run   ·   "
       "12. Viva Q&A Drill   ·   13. Limitations & Future Work")
para(toc, 9.5, False, GRAY)
doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

# ═══════════════ 1 ═══════════════
doc.add_heading("1. Executive Summary", 1)
para("Manual roll-call wastes 5–10 minutes of every lecture, is vulnerable to proxy attendance, and produces "
     "registers that cannot be audited. This project replaces that ritual with a single photograph. The teacher "
     "uploads one picture of the classroom; a face-recognition engine detects every face, converts each into a "
     "128-dimension mathematical signature, and compares it against enrolled students.")
para("The defining design decision is the Human-in-the-Loop (HITL) policy. High-confidence matches (distance "
     "≤ 0.45) arrive pre-approved; medium-confidence matches (0.45–0.60) are shown side-by-side with the "
     "registered portrait for the teacher to confirm or correct; unmatched faces are Unknown and can only be "
     "assigned by a human. Every stored mark records HOW it was made (auto / review / manual / system-absent), "
     "the AI confidence %, and which teacher verified it — a fully auditable register.")
para("Around that core the system ships complete: role-based access (admin + teachers), live analytics, an "
     "at-risk alert dashboard with 7-day trends, CSV exports, scheduled email digests, a PIN-protected student "
     "self-service portal, hardened security (CSRF, rate limiting, hashed credentials, security headers), Docker "
     "deployment on Render, and 61 automated tests plus a 20-point live deployment verification — all passing.")

# ═══════════════ 2 ═══════════════
doc.add_heading("2. Problem Statement & Objectives", 1)
doc.add_heading("Problems addressed", 2)
bullets([
    "Roll-call consumes 5–10 minutes of every lecture (≈30+ hours per subject per semester).",
    "Proxy attendance: one student answering for an absent friend is undetectable on paper.",
    "Paper registers are error-prone, easy to lose, and impossible to audit after the fact.",
    "Students below the 75% requirement are discovered too late — at exam form filling.",
])
doc.add_heading("Objectives", 2)
bullets([
    "Mark attendance for an entire class from one photo, in seconds, from any phone browser.",
    "Keep the teacher as the final authority: the AI suggests, the human decides (HITL).",
    "Record provenance for every mark: method, AI confidence %, and verifying teacher.",
    "Surface at-risk students early via thresholds, 7-day trends, alerts and email digests.",
    "Protect people and data: hashed credentials, CSRF, rate limiting, no real biometrics in git.",
    "Deploy on commodity infrastructure (Docker, free tier) with zero paid dependencies.",
])

# ═══════════════ 3 ═══════════════
doc.add_heading("3. System Architecture", 1)
code_block(
    "┌────────────────────────────────────────────────────────────────┐\n"
    "│ FRONTEND — server-rendered Jinja2 templates + custom CSS       │\n"
    "│  dashboard · verification UI (HITL) · students · analytics ·   │\n"
    "│  alerts · admin · student portal (/me)                         │\n"
    "└──────────────────────────┬─────────────────────────────────────┘\n"
    "                           ▼\n"
    "┌────────────────────────────────────────────────────────────────┐\n"
    "│ BACKEND — Flask application (app.py, 23 routes)                │\n"
    "│  auth & roles · CSRF · rate limiting · security headers        │\n"
    "│  HITL confirm logic · reports.py (stats) · mailer.py (email)   │\n"
    "└──────────────────────────┬─────────────────────────────────────┘\n"
    "                           ▼\n"
    "┌────────────────────────────────────────────────────────────────┐\n"
    "│ AI CORE — face_engine/                                         │\n"
    "│  detector.py (HOG detection + cropping)                        │\n"
    "│  encoder.py (enrollment → 128-d encodings)                     │\n"
    "│  recognizer.py (matching + 3-band policy + annotations)        │\n"
    "└──────────────────────────┬─────────────────────────────────────┘\n"
    "                           ▼\n"
    "┌────────────────────────────────────────────────────────────────┐\n"
    "│ DATA — SQLite (Postgres-ready) + files                         │\n"
    "│  teachers · students · subjects · attendance_sessions ·        │\n"
    "│  attendance   |   face_encodings.pkl · student_faces/          │\n"
    "└────────────────────────────────────────────────────────────────┘")
para("The browser talks only to Flask. Flask is the only writer of the database. The face engine is a pure "
     "Python library — the web layer never touches dlib directly, which means the engine can be swapped "
     "(e.g. InsightFace/YOLOv8) without changing a single route.", 9.5, color=GRAY)

# ═══════════════ 4 ═══════════════
doc.add_heading("4. Complete Technology Stack", 1)
table(["Layer", "Technology", "Why it is used / where"], [
    ["Language", "Python 3.13 (3.11 in Docker)", "AI/ML ecosystem, readability, team familiarity"],
    ["Web framework", "Flask 3.x + Jinja2", "Lightweight routing + server-rendered templates; ideal for an AI-backed MVP"],
    ["ORM / DB", "Flask-SQLAlchemy + SQLite (Postgres-ready)", "Type-safe models, unique constraints, zero-config dev DB; DATABASE_URL swaps in hosted Postgres"],
    ["Authentication", "Flask-Login + Werkzeug hashing", "Session-based teacher auth; PBKDF2/scrypt hashing (never plain text)"],
    ["Face detection", "dlib HOG (via face_recognition)", "Fast CPU detection of frontal faces; runs on free-tier hardware"],
    ["Face identity", "dlib ResNet — 128-d embeddings", "Deep metric embeddings: same person maps to nearby points in 128-d space"],
    ["Matching", "Euclidean distance (NumPy)", "One vector subtraction per enrolled student — microseconds, no model call"],
    ["Image processing", "OpenCV 4.11 (headless in Docker)", "Crop faces, draw annotated verdicts, encode JPEG outputs"],
    ["Photo normalization", "Pillow (EXIF + Lanczos resize)", "Fixes rotated phone photos (EXIF) and tames 12MP images for 512MB RAM"],
    ["Exports", "pandas", "One-line CSV export of raw log and student summaries"],
    ["Email", "smtplib (STARTTLS) + HTML template", "Console backend for demos, real SMTP via env vars; cron CLI included"],
    ["Production server", "Gunicorn (WSGI)", "Worker count tuned via WEB_CONCURRENCY (free tier: 1)"],
    ["Packaging", "Docker + docker-compose", "Same image everywhere; data/ volume persists DB + portraits"],
    ["Hosting", "Render.com (free tier)", "Auto-builds the Dockerfile, public HTTPS URL, zero-cost demo"],
    ["Frontend styling", "Hand-written CSS3", "Glassmorphism nav, gradients, hover states — zero CDN dependency, works offline"],
    ["Version control", "Git + GitHub", "Single source of truth; verified remote sync"],
], widths=[1.2, 2.1, 3.5])
callout("Why face_recognition (dlib) and not a cloud face API? It runs 100% offline and free, is well "
        "documented, and its distance metric gives interpretable confidence bands — exactly what the "
        "Human-in-the-Loop policy needs.")

# ═══════════════ 5 ═══════════════
doc.add_page_break()
doc.add_heading("5. The Face-Recognition Engine (Technical Heart)", 1)
doc.add_heading("5.1 Recognition pipeline", 2)
bullets([
    "STEP 1 — Detection (HOG): the image is scanned for face-like gradient patterns → boxes (top, right, bottom, left). Fast on CPU; a 'cnn' model is available for GPU accuracy.",
    "STEP 2 — Embedding: each face is aligned and passed through a ResNet producing 128 numbers (the encoding). A fingerprint: the same person lands close together regardless of lighting, angle or camera.",
    "STEP 3 — Matching: each classroom encoding is compared to every enrolled encoding with Euclidean distance; smallest wins. Microseconds of math.",
    "STEP 4 — Policy: the winning distance maps to one of three verdicts (table below).",
    "STEP 5 — Output: structured results (id, distance, similarity %, verdict) + a color-annotated photo (green/amber/red boxes) + face crops for the comparison UI.",
])
doc.add_heading("5.2 The three-band Human-in-the-Loop policy", 2)
table(["Distance d", "Verdict", "What the teacher sees", "Stored method"], [
    ["d ≤ 0.45", "AUTO-APPROVED (green)", "Pre-checked Present card with similarity bar; teacher can still uncheck", "auto"],
    ["0.45 < d ≤ 0.60", "NEEDS REVIEW (amber)", "Side-by-side: classroom face VS registered portrait; confirm or correct via dropdown", "review (confirmed) / manual (corrected)"],
    ["nobody ≤ 0.60", "UNKNOWN (red)", "Face crop with '?'; teacher assigns a roll number — or leaves absent", "manual / stays absent"],
], widths=[1.1, 1.5, 2.9, 1.3])
para("Everyone the teacher does not mark is written ABSENT (method=system). One photo therefore produces a "
     "complete register — and a missed detection can never inflate attendance.", 9.5, color=GRAY)
doc.add_heading("5.3 Measured engine results (reproducible via scripts)", 2)
table(["Probe", "Result"], [
    ["Group photo: 6 students, 2 loose rows", "6/6 faces detected and enrolled"],
    ["Augmented copy (mirrored, −18% brightness, 0.85×, JPEG-70)", "6/6 re-identified; distances 0.188–0.262 → all auto-approved"],
    ["Leave-one-out control (store WITHOUT one student)", "That student rejected at distance 0.726 (≫ 0.60) — no false match"],
    ["Stranger portrait (never enrolled)", "Distance 0.802 → Unknown; never auto-approved"],
    ["Stress test (0.55× + blur + underexposure + JPEG-45)", "2 detectable faces at 0.470 / 0.583 → correctly NEEDS REVIEW; 0 false auto-approvals"],
    ["Simulated phone photo (pixels rotated 90° + EXIF flag)", "Before fix: 0/6 detected. After EXIF normalization: 6/6 auto-approved"],
], widths=[3.4, 3.4])
callout("Blueprint correction we defend in the viva: the original plan auto-approved at 'confidence ≥ 85%' "
        "computed as 1 − distance, i.e. distance ≤ 0.15. Real same-person dlib distances land at 0.20–0.45, so "
        "that rule would send EVERY genuine student to manual review. Our bands (0.45 / 0.60) follow dlib "
        "conventions and are validated by the probes above.")
doc.add_heading("5.4 Real-world photo hardening (EXIF + resolution)", 2)
para("Phone cameras store pixels sideways and add an EXIF flag telling viewers to rotate. OpenCV and dlib "
     "IGNORE that flag — an unprocessed phone upload presents sideways faces and detection fails (proven: 0/6). "
     "Every upload is normalized with Pillow: EXIF-transpose to true upright, convert to RGB, downscale to "
     "2000px long side (1600 for enrollment portraits). This also keeps 12MP photos fast and memory-safe on "
     "the 512MB free tier.")

doc.add_heading("5.5 Real-classroom dataset — 11 real students enrolled & recognized", 2)
para("The engine was validated on a real class dataset: 11 student portraits (extracted from the class "
     "photo-roster PDF) enrolled under rolls US001-US011 via scripts/bulk_enroll.py — each portrait "
     "EXIF-normalized and encoded exactly like web enrollment. Results: every student recognized as "
     "themselves in four independent variants (original, mirrored, dimmed -35 percent, downscaled 55 "
     "percent) — 44/44 correct, all in the auto-approve band (distances 0.017-0.192). Impostor "
     "separation held across all 55 classmate pairs (closest 0.453, above the 0.45 auto-approve line). "
     "A single group frame containing all eleven faces produced 11 detections and 11 correct roll "
     "numbers, every face auto-approved — the exact flow the demo uses.")
table(["Roll", "Student", "Self-test (orig/mirror/dim/small)", "Group frame"], [
    ["US001", "Utkarsh Sharma", "4/4 auto-approve", "auto-approved"],
    ["US002", "Riya Negi", "4/4 auto-approve", "auto-approved"],
    ["US003", "Sujoy Maity", "4/4 auto-approve", "auto-approved"],
    ["US004", "Priyanka Chavan", "4/4 auto-approve", "auto-approved"],
    ["US005", "Suraj Singh", "4/4 auto-approve", "auto-approved"],
    ["US006", "Akshata Patenkar", "4/4 auto-approve", "auto-approved"],
    ["US007", "Prachi Gupta", "4/4 auto-approve", "auto-approved"],
    ["US008", "Riya Sawant", "4/4 auto-approve", "auto-approved"],
    ["US009", "Pratiksha Wakshe", "4/4 auto-approve", "auto-approved"],
    ["US010", "Aditya Mehra", "4/4 auto-approve", "auto-approved"],
    ["US011", "Darshana Gupta", "4/4 auto-approve", "auto-approved"],
], widths=[0.8, 2.0, 2.3, 1.7])

# proof images
for img, cap in (("data/outputs/annotated_full.jpg",
                  "Figure 1 — Good capture: all six students detected, matched, auto-approved (green)."),
                 ("data/outputs/annotated_hard.jpg",
                  "Figure 2 — Degraded capture: only 2 faces detectable, both correctly routed to NEEDS REVIEW (amber).")):
    pth = ROOT / img
    if pth.exists():
        doc.add_picture(str(pth), width=Inches(6.2))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        para(cap, 9, False, GRAY, "center")

# ═══════════════ 6 ═══════════════
doc.add_page_break()
doc.add_heading("6. Complete Feature Walkthrough (Every Module)", 1)
feats = [
    ("6.1 Authentication & roles",
     "Teachers log in with email + password (Werkzeug-hashed). Two roles: ADMIN (full visibility, manages "
     "accounts and subjects) and TEACHER (sees and marks only assigned subjects and own sessions). Failed "
     "logins are rate-limited per IP: 5 failures per 60 seconds. Demo: log in as arjun@college.edu — the Admin "
     "page returns 403."),
    ("6.2 Teacher dashboard",
     "Landing page: today's present count, your subjects, the 75% at-risk line, and the 8 most recent sessions "
     "with verified/pending status. The upload form lives here, including the one-click 'Try the demo photo' "
     "button that runs the bundled classroom shot without needing a file."),
    ("6.3 Photo upload + AI pass (POST /take_attendance)",
     "Validates extension (.jpg/.jpeg/.png) and 16MB cap, saves with a UUID name, normalizes (EXIF transpose, "
     "RGB, downscale), then runs the engine. Results persist as a PENDING AttendanceSession with a JSON "
     "payload; face crops and a color-annotated photo are written for the verification screen. Duplicate "
     "detections of the same student are deduplicated. Zero faces → friendly error, nothing saved."),
    ("6.4 Verification page — the HITL core",
     "Summary chips (auto/review/unknown counts); 'What the AI saw' annotated photo; GREEN pre-checked cards; "
     "AMBER side-by-side VS comparison with an identity dropdown preselected to the AI guess (changing it "
     "CORRECTS the AI → stored as manual); RED unknown cards with a dropdown of unmatched students; an "
     "'Also present?' multiselect for students the photo missed; sticky confirm bar warning that everyone "
     "unmarked will be recorded ABSENT."),
    ("6.5 Confirmation & the auditable register",
     "Decisions are written transactionally: AI-guess confirmations store method auto/review with confidence %; "
     "changed identities store manual; extra-present stores manual; the rest of the roster stores Absent "
     "(system). Every row records verified_by and links to the session. Upsert per (student, subject, date) "
     "means same-day re-marks UPDATE instead of duplicating."),
    ("6.6 Sessions & provenance",
     "Each upload is a session: subject, teacher, timestamp, original photo, AI verdicts JSON, status "
     "pending→verified, decision time. The detail page shows the annotated photo plus present/absent breakdown "
     "with per-student method chips (auto 76% / review 53% / manual) — an audit trail months later."),
    ("6.7 Student enrollment & management (/students)",
     "Enroll with roll number, name, department, semester, optional portal PIN and a portrait. The portrait is "
     "normalized (EXIF + 1600px) and encoded immediately — enrollment fails clearly if no single face is found. "
     "Roster shows live attendance bars. CLI alternative: scripts/enroll_students.py --rebuild / --add / --list."),
    ("6.8 Analytics (/analytics)",
     "Overall + today donuts, at-risk counter, a pure-SVG daily trend chart with a red dashed 75% line, "
     "per-student and per-subject bars. Color language: green ≥ 75%, amber 50–74%, red < 50%. CSV buttons on top."),
    ("6.9 Alerts dashboard (/alerts)",
     "The teacher's daily action list. AT-RISK (< 75%): overall %, last-7-days %, trend arrow (recent minus "
     "overall), each student's WORST subject (≥ 3 classes). BORDERLINE (< 85%) for early intervention. One "
     "implementation (reports.py) powers alerts + CSV + email — single source of truth."),
    ("6.10 CSV exports",
     "attendance_raw.csv (every mark: date, time, student, subject, status, method, AI confidence, verified by) "
     "and students_summary.csv (totals, %, last-7-day %, trend delta, worst subject, at-risk flag)."),
    ("6.11 Email digest (+ cron CLI)",
     "Branded HTML email (at-risk table with trend arrows, borderline list, suggested action) to all teachers. "
     "CONSOLE backend renders the exact email to data/outputs/emails/ for demos (preview at "
     "/alerts/email/preview); SMTP via EMAIL_BACKEND=smtp + SMTP_* env vars. Cron: '0 8 * * * python "
     "scripts/send_alerts.py'."),
    ("6.12 Admin panel (/admin, admin-only)",
     "Create teacher/admin accounts (password ≥ 6 chars), add subjects, reassign ownership inline. Server-side "
     "enforcement: teachers get 403 on subjects/sessions that are not theirs. Seed: admin owns CS201+CS302, "
     "Prof. Arjun Nair owns CS405."),
    ("6.13 Student self-service portal (/me, public)",
     "Roll number + PIN (hashed; demo 1234) → attendance donut, subject-wise bars, recent history, prominent "
     "below-75% warning. Generic errors (no user enumeration), shared rate limiting. Read-only: disputes go to "
     "the teacher."),
    ("6.14 Security model (cross-cutting)",
     "CSRF token on every POST (400 without it); security headers (CSP self-only, nosniff, DENY frames, "
     "referrer policy); rate limiting 5 fails/60s per IP on login AND portal; HttpOnly + SameSite cookies; "
     "16MB upload cap + extension allow-list; login-gated regex-validated media routes (traversal blocked); "
     "hashed passwords and PINs; biometrics live in ONE engine-owned pickle, never the DB; repo contains only "
     "AI-generated faces."),
    ("6.15 Deployment (Docker + Render)",
     "Dockerfile: python3.11-slim + prebuilt dlib-bin (no compile) + explicit deps; face_recognition installed "
     "--no-deps on top (Pillow/Click/models listed manually — the missing-Pillow boot bug taught us that). "
     "Gunicorn via WEB_CONCURRENCY (default 1 for 512MB). compose mounts ./data. Render auto-builds; first boot "
     "creates schema + seeds demo data race-safely (file lock + IntegrityError fallback — fixed a real "
     "two-worker crash). Free tier: sleeps ~15 min idle, auto-reseeds on boot."),
]
for title, body in feats:
    doc.add_heading(title, 2)
    para(body)

# ═══════════════ 7 ═══════════════
doc.add_page_break()
doc.add_heading("7. Database Design (5 tables)", 1)
table(["Table", "Columns & purpose"], [
    ["teachers", "id PK | name | email UNIQUE | password_hash (scrypt) | role ('admin'|'teacher')"],
    ["students", "id PK | student_id UNIQUE (roll) | first/last name | email | department | semester | photo_path | portal_pin (hashed) | active"],
    ["subjects", "id PK | name | code UNIQUE (CS201…) | teacher_id FK — course catalogue + ownership"],
    ["attendance_sessions", "id PK | subject_id FK | teacher_id FK | photo_path | results_json (AI verdicts) | status pending→verified | created_at | decided_at"],
    ["attendance", "id PK | session_id FK | student_id FK | subject_id FK | date | time | status | confidence FLOAT | method auto/review/manual/system | verified_by FK | created_at. UNIQUE(student, subject, date) → re-marks UPDATE, never duplicate"],
], widths=[1.6, 5.2])
callout("Design decision to defend: biometric encodings are NOT in the database. One writer owns them "
        "(face_engine's face_encodings.pkl), eliminating two-source-of-truth sync bugs. Older DBs are migrated "
        "in place (ALTER TABLE + backfill).")

# ═══════════════ 8 ═══════════════
doc.add_heading("8. Complete Route Map (23 endpoints)", 1)
table(["Method", "Route", "Purpose", "Access"], [
    ["GET", "/", "Redirect to dashboard/login", "public"],
    ["GET/POST", "/login", "Login (rate-limited)", "public"],
    ["GET", "/logout", "Clear session", "logged in"],
    ["GET", "/teacher/dashboard", "Stats, subjects, upload form, recent sessions", "teacher (filtered)"],
    ["POST", "/take_attendance", "Upload → normalize → AI pass → pending session", "owner teacher"],
    ["GET", "/session/<id>/verify", "HITL verification page", "owner/admin"],
    ["POST", "/session/<id>/confirm", "Write final register with provenance", "owner/admin"],
    ["GET", "/session/<id>", "Session detail + annotated photo", "owner/admin"],
    ["GET/POST", "/students", "Roster + enroll (live face encoding)", "any staff"],
    ["GET", "/analytics", "Donuts, SVG trend, per-student/subject bars", "any staff"],
    ["GET", "/alerts", "At-risk + borderline tables", "any staff"],
    ["GET", "/alerts/email/preview", "Render the digest email", "any staff"],
    ["POST", "/alerts/email/send", "Send digest (console/SMTP)", "any staff"],
    ["GET", "/export/attendance.csv", "Raw log with provenance", "any staff"],
    ["GET", "/export/students.csv", "Per-student summary + risk flag", "any staff"],
    ["GET", "/admin", "Accounts + subjects management", "ADMIN (403 else)"],
    ["POST", "/admin/teachers/add", "Create teacher/admin", "ADMIN"],
    ["POST", "/admin/subjects/add", "Create subject", "ADMIN"],
    ["POST", "/admin/subjects/<id>/assign", "Reassign subject", "ADMIN"],
    ["GET/POST", "/me", "Student portal (roll + PIN)", "public (PIN)"],
    ["GET", "/student?student_id=", "Staff-side student lookup", "any staff"],
    ["GET", "/media/<sid>/<name>", "Session crops/annotated image", "logged in, regex-guarded"],
    ["GET", "/photo/<name>", "Enrollment portraits", "logged in, regex-guarded"],
], widths=[0.8, 1.9, 2.9, 1.2])

# ═══════════════ 9 ═══════════════
doc.add_page_break()
doc.add_heading("9. Project Structure (what every file does)", 1)
code_block(
    "attendance-system/\n"
    "├── app.py                  Flask app: 23 routes, HITL confirm, analytics, roles, portal, security\n"
    "├── config.py               Bands (0.45/0.60), 75% threshold, rate limits, paths, EMAIL/DATABASE envs\n"
    "├── face_engine/\n"
    "│   ├── detector.py         HOG detection → DetectedFace(location, encoding); crop_face\n"
    "│   ├── encoder.py          FaceEncodingStore: enroll (dominant face, replace-on-re-enroll), pickle I/O\n"
    "│   └── recognizer.py       FaceRecognizer.recognize() → 3-band verdicts; .annotate() → color JPEG\n"
    "├── database/\n"
    "│   ├── models.py           5 SQLAlchemy models\n"
    "│   └── seed.py             Idempotent demo seed + migrations + race-safe file lock\n"
    "├── reports.py              ONE implementation of per-student stats (UI + CSV + email share it)\n"
    "├── mailer.py               Digest builder + console/SMTP backends\n"
    "├── templates/ (10 pages)   base(glass nav) · login · dashboard · verify(HITL) · session · students ·\n"
    "│                           analytics · alerts · admin · portal · email\n"
    "├── static/style.css        Design system: gradients, glass, cards, chips, bars, responsive menu\n"
    "├── scripts/                setup_env.sh · enroll_students.py · run_phase2_demo.py · stress_test.py ·\n"
    "│                           send_alerts.py · demo_photo.py · make_project_pdf.py · make_project_docx.py\n"
    "├── tests/                  test_face_engine.py (11) · test_web_flow.py (50)\n"
    "├── docs/                   PROJECT_REPORT.md · DEMO.md · DEPLOY.md · PDF guide · this report\n"
    "├── Dockerfile              python3.11-slim + dlib-bin + gunicorn (WEB_CONCURRENCY aware)\n"
    "├── docker-compose.yml      Port 8000 + ./data volume\n"
    "└── data/                   student_faces/ · uploads/ · outputs/ · face_encodings.pkl · attendance.db")

# ═══════════════ 10 ═══════════════
doc.add_heading("10. Testing & Quality Evidence", 1)
table(["Suite / probe", "Count", "What it proves"], [
    ["tests/test_face_engine.py", "11 PASS", "Enrollment integrity (128-d), re-identification, augmentation robustness, stranger rejection"],
    ["tests/test_web_flow.py", "50 PASS", "CSRF, auth, all 3 HITL branches, absent-by-default, correction→manual, enrollment, analytics, CSVs, alerts, email, roles+403s, portal, media ACL, traversal, headers, rate limit"],
    ["Live deployment smoke (2026-09-21)", "20/20 PASS", "Every page, the full AI flow, exports, roles and portal on the production Render URL"],
    ["Accuracy probes (leave-one-out, stranger, stress)", "5 probes", "0.188–0.262 same-person | 0.726 rejection | 0.802 stranger | 0 false auto-approvals"],
    ["EXIF phone-photo probe", "0/6 → 6/6", "Real-world rotation handling works"],
    ["Real-class dataset (11 students)", "44/44 + 11/11", "Self-recognition in 4 variants; 11-face group frame; 55-pair impostor separation"],
], widths=[1.9, 0.9, 4.0])
para("Reproduce: python tests/test_web_flow.py | pytest tests/ -v | python scripts/run_phase2_demo.py | "
     "python scripts/stress_test.py | python scripts/demo_photo.py data/uploads/classroom_demo_hard.jpg", 9.5, color=GRAY)

# ═══════════════ 11 ═══════════════
doc.add_heading("11. How to Run It", 1)
code_block(
    "Local : bash scripts/setup_env.sh  →  python app.py  →  http://localhost:8000\n"
    "Docker: docker compose up --build\n"
    "Cloud : https://autoattendance-xjeg.onrender.com  (Render auto-builds from GitHub)\n"
    "\n"
    "Demo flow: login teacher@college.edu / teacher123 → 'Try the demo photo' →\n"
    "verify (green/amber/red) → Confirm → Analytics → Alerts → portal /me (ST005 + 1234)")

# ═══════════════ 12 ═══════════════
doc.add_page_break()
doc.add_heading("12. Viva Q&A Drill (likely questions, ready answers)", 1)
table(["Question", "Your answer"], [
    ["How does the AI recognize a face?", "HOG finds the face; a ResNet converts it to 128 numbers; we compare those to every enrolled student with Euclidean distance and take the closest."],
    ["What is a 128-d encoding?", "A deep-metric embedding: a point in 128-d space where the same person's photos cluster tightly regardless of lighting/angle — a mathematical fingerprint."],
    ["Why distance, not a classifier percentage?", "Distance is interpretable and thresholdable: honest bands (0.45 auto / 0.60 review) route uncertainty to a human instead of guessing."],
    ["Why did you change the blueprint's 85% threshold?", "85% as 1−distance means distance 0.15 — genuine matches never get that close (ours: 0.19–0.26), so every student would need manual review. We validated bands empirically."],
    ["What stops the AI marking a stranger present?", "Three layers: the 0.60 tolerance (strangers measure ≈0.80), the red Unknown flow requiring human assignment, and absent-by-default. Leave-one-out proves rejection at 0.726."],
    ["Two students look alike?", "Their distance lands in the amber band → teacher reviews side-by-side and corrects the dropdown; stored as method=manual, so we know when the AI erred."],
    ["Can someone cheat with a printed photo?", "A 2-D photo can fool pure matching — honest limitation. Production adds liveness detection (blink/depth). In the report's future work."],
    ["What if the photo is blurry/far?", "Some faces aren't detected → they default Absent (never wrongly present); the teacher uses the 'Also present?' list. Degraded probes never auto-approved anything."],
    ["Why SQLite and not MySQL?", "Zero-config for demo, fast at college scale; SQLAlchemy + DATABASE_URL make hosted Postgres a config change, not a rewrite."],
    ["What is CSRF and how did you stop it?", "Cross-Site Request Forgery — attacker form posts as a logged-in user. Every POST must carry the session-embedded token; otherwise 400."],
    ["How are passwords protected?", "Werkzeug scrypt/PBKDF2 hashing with salts — irreversible. Portal PINs hashed identically."],
    ["Why is the data trustworthy?", "Every mark stores method, AI confidence %, verifying teacher, and links to the session with the annotated photo — a full audit trail."],
    ["How does it handle real phone photos?", "EXIF orientation auto-rotation + downscaling on upload; simulation: 0/6 detection before the fix, 6/6 after."],
    ["How would you scale to 500 students?", "Vectorized distance already handles thousands of encodings in microseconds; Postgres (config-only), GPU/CNN detector or InsightFace, cached encoding matrix, background email workers."],
    ["Is face data safe?", "Repo contains only AI-generated faces; real biometrics stay in a git-ignored volume. Production requires consent + retention policy (DPDP Act) — stated in the report."],
    ["Hardest bug you fixed?", "Two gunicorn workers seeding the empty DB simultaneously on first deploy → UNIQUE constraint crash. Fixed with an exclusive file lock + fallback; verified on a fresh-DB deploy."],
], widths=[2.4, 4.4])

# ═══════════════ 13 ═══════════════
doc.add_heading("13. Limitations & Future Work", 1)
bullets([
    "Detection ceiling: extreme distance/blur drops faces (absent-by-default + manual list mitigates).",
    "No liveness/anti-spoofing yet (printed-photo attack) — blink or depth-based liveness is future work.",
    "Free tier: sleeps after idle; ephemeral disk on redeploys (auto-reseed keeps demos working).",
    "Accuracy on larger real-world cohorts should be re-validated (bias/lighting audits) before production.",
    "Roadmap: InsightFace/YOLOv8 engine behind the same interface; OTP-based student identity; parent email "
    "alerts; admin PIN-reset UI; timetable-aware absent messaging.",
])
doc.add_paragraph()
callout("One-line summary for your viva: 'The AI does in three seconds what roll-call does in five minutes — "
        "and a teacher, not an algorithm, signs every single mark.'", fill="E8F9F0")

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(str(OUT))
print(f"DOCX generated: {OUT}")
