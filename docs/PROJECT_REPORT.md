# Automated Student Attendance System
## Project Report — PBL Submission

| | |
|---|---|
| **Project** | Automated Student Attendance System (AI-suggested, teacher-verified) |
| **Core idea** | Classroom photo → face recognition → pre-filled attendance → teacher confirms/corrects (Human-in-the-Loop) |
| **Stack** | Python 3.13, Flask, SQLAlchemy (SQLite), dlib `face_recognition`, OpenCV, pandas |
| **Status** | Phases 1–6 complete, 61 automated checks passing, deployed via Docker |
| **Repository** | github.com/AA7304-MEH/automated-attendance-system--pbl- |

> All student faces used in this project are AI-generated (synthetic). No real
> biometric data is stored in the repository.

---

## 1. Abstract

Manual roll-call attendance wastes 5–10 minutes of every lecture and is
vulnerable to proxy attendance. This project automates attendance from a
single classroom photograph: a face-recognition engine detects every face,
computes 128-dimensional embeddings, and matches them against enrolled
students. Instead of blindly trusting the AI, the system implements a
**three-state Human-in-the-Loop (HITL) policy** — high-confidence matches are
pre-approved, moderate-confidence matches are routed to the teacher with a
side-by-side visual comparison, and unknown faces must be explicitly assigned
by the teacher. Every recorded mark carries its provenance (`auto`, `review`,
`manual`, `system`) and the AI's confidence score, making the register fully
auditable. Analytics, alerts, CSV exports, an email digest, a student
self-service portal, and role-based multi-teacher access complete the system.

## 2. Problem Statement & Objectives

**Problems addressed**
1. Time lost to roll-call in every lecture.
2. Proxy (buddy) attendance fraud.
3. Manual registers are error-prone and hard to audit.
4. Students below the attendance requirement are noticed too late.

**Objectives**
1. Mark attendance for a whole class from one photo in seconds.
2. Keep a human teacher as the final authority on every mark (HITL).
3. Record *how* each mark was made and *how confident* the AI was.
4. Surface at-risk students early (thresholds, trends, alerts).
5. Protect the system and the data (auth, roles, CSRF, hashing, no biometrics in git).

## 3. System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│ FRONTEND (server-rendered Jinja2 + dependency-free CSS)        │
│  dashboard · verify UI · students · analytics · alerts ·       │
│  admin · student portal (/me)                                  │
└───────────────────────────┬────────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────────┐
│ BACKEND (Flask)                                                │
│  auth+roles · CSRF · rate limiting · sessions · uploads        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ face_engine (Phase 2 core)                               │  │
│  │  detector.py   HOG face detection + cropping             │  │
│  │  encoder.py    enrollment → 128-d encodings (pickle DB)  │  │
│  │  recognizer.py matching + 3-state HITL policy            │  │
│  └──────────────────────────────────────────────────────────┘  │
│  reports.py (single source of truth for all risk stats)        │
│  mailer.py  (console / SMTP email digests)                     │
└───────────────────────────┬────────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────────┐
│ DATA                                                           │
│  SQLite: teachers · students · subjects ·                      │
│          attendance_sessions · attendance                      │
│  face_encodings.pkl (128-d biometric templates)                │
│  data/student_faces/ (enrollment portraits)                    │
└────────────────────────────────────────────────────────────────┘
```

## 4. Methodology

### 4.1 Face representation
Every face is converted to a **128-dimensional embedding** by dlib's
ResNet (via `face_recognition`). Identical principle to a fingerprint: two
photos of the same person map to nearby points; different people map far
apart. Comparison is Euclidean **distance** (0 = identical), so the system is
invariant to lighting, pose and camera differences by construction.

### 4.2 The three-state HITL policy (key differentiator)

| Distance d | Verdict | UI behaviour | Recorded method |
|---|---|---|---|
| d ≤ 0.45 | `auto_approved` | green card, **pre-checked** present | `auto` |
| 0.45 < d ≤ 0.60 | `needs_review` | amber card, side-by-side crops, teacher confirms or corrects via dropdown | `review` (confirmed) / `manual` (corrected) |
| nobody ≤ 0.60 | `unknown` | red card, teacher assigns from roster — or leaves absent | `manual` / stays absent |

Everyone the teacher does not mark is recorded **Absent** by default, so
uploading a photo produces a complete register, not a present-only list.

> **Blueprint correction (important):** the original project plan used
> "confidence ≥ 85%" computed as `1 − distance`, i.e. auto-approve only when
> distance ≤ 0.15. Real same-person dlib distances land at **0.20–0.45**, so
> that rule would push virtually every genuine match into manual review. The
> shipped thresholds (0.45 / 0.60) follow dlib's documented norms and were
> validated empirically (§7).

### 4.3 Why the teacher stays in the loop
AI-only attendance fails in unacceptable ways: an un-enrolled visitor can be
absent-without-record, twins/similar faces get confused, and low-quality
photos silently drop students. The verify page therefore shows the teacher
**what the AI saw** (annotated photo), separates the three confidence bands,
and lets them correct anything with one click. Absent-by-default means a
missing detection can never inflate attendance.

## 5. Database Design

| Table | Purpose / key columns |
|---|---|
| `teachers` | staff accounts: name, email, **password_hash**, **role** (`admin`/`teacher`) |
| `students` | roll no, names, dept, semester, photo_path, **portal_pin (hashed)**, active |
| `subjects` | code, name, assigned `teacher_id` |
| `attendance_sessions` | one photo-upload = one recognition run: subject, teacher, uploaded photo, AI results JSON, status `pending`→`verified` |
| `attendance` | one row per student×subject×date (unique constraint): status, **method** (`auto`/`review`/`manual`/`system`), **confidence %**, `verified_by`, session link |

Biometric templates live in a single pickle (`face_encodings.pkl`) owned
exclusively by `face_engine` — the relational DB never duplicates encodings,
eliminating sync bugs.

## 6. Feature Summary

| Phase | Delivered |
|---|---|
| 1 | Reproducible environment (prebuilt dlib strategy, 30-second cold start) |
| 2 | Face engine: detection, enrollment CLI, 3-state recognition, annotated output |
| 3 | Web app: login, upload, **verification UI**, attendance persistence, analytics |
| 4 | CSV exports (raw log + student summary), alerts dashboard, **Dockerfile** |
| 5 | **Email digests** (console/SMTP + cron CLI), **multi-teacher + admin roles**, security hardening |
| 6 | **Student self-service portal** (`/me`, roll + hashed PIN), formal report (this document) |

## 7. Testing & Results

### 7.1 Engine accuracy probes (measured, reproducible via `scripts/run_phase2_demo.py`)

| Probe | Result |
|---|---|
| Group photo (6 synthetic students) | **6/6 faces detected**, enrolled |
| Same photo augmented (mirrored, −18% brightness, 0.85×, JPEG-70) | **6/6 re-identified**, distances **0.188–0.262** → all `auto_approved` (≤ 0.45) |
| Leave-one-out control (store without ST006) | ST006 rejected at distance **0.726** (≫ 0.60) → no false match |
| Stranger portrait (never enrolled) | distance **0.802** → `unknown`, never auto-approved |
| Stress test (0.55×, blur, underexposure, JPEG-45) | 2 detectable faces at **0.470 / 0.583** → correctly routed to `needs_review`; **0 false auto-approvals** |

The probes demonstrate both properties a marker cares about: the engine
**recognises genuine students** under realistic image degradation, and it
**rejects everyone it was never taught**.

### 7.2 Automated test suites

| Suite | Checks | Coverage |
|---|---|---|
| `tests/test_face_engine.py` | 11 | enrollment integrity, re-identification, augmentation robustness, stranger rejection |
| `tests/test_web_flow.py` | **50** | CSRF, auth, full HITL flow (auto/review/unknown + teacher correction), absent-by-default, enrollment, analytics, CSVs, alerts, email digest, roles & ownership (403s), media access control, path traversal, security headers, portal, login rate limiting |

**Result: 61/61 passing** on a fresh database (and repeatable on an existing one).

### 7.3 Manual verification
The live app was additionally driven end-to-end over HTTP (login → demo-photo
upload → verify → confirm → analytics → alerts → email preview/send → portal).

## 8. Security

- Passwords and portal PINs stored **hashed** (PBKDF2 via Werkzeug).
- **CSRF token** required on every POST (verified by tests).
- **Security headers**: Content-Security-Policy, X-Content-Type-Options,
  X-Frame-Options: DENY, Referrer-Policy.
- **Login rate limiting**: 5 failed attempts/min/IP (staff login and portal).
- **Role-based access**: teachers see/mark only their subjects and sessions
  (ownership checks return 403); only admins reach `/admin`.
- Media routes are login-gated and regex-validated (path traversal blocked).
- **Privacy by design**: repository contains only AI-generated faces; real
  biometrics belong in a git-ignored local folder (see `.gitignore` guidance).

## 9. Deployment

```bash
docker build -t autoattendance .
docker run -p 8000:8000 -v $(pwd)/data:/app/data autoattendance
# or: docker compose up
```

First boot auto-creates the database, seeds demo data and builds the encoding
DB; `data/` is a volume so everything persists. For production: run behind a
reverse proxy with HTTPS (gunicorn is included in the image).

## 10. Limitations & Ethical Considerations

1. **Detection limits**: severely blurred/occluded faces may not be detected;
   the absent-by-default + "also present?" list prevents wrong records.
2. **Not anti-spoofing**: a printed photo could fool pure 2-D matching;
   liveness detection (depth/IR or blink detection) is future work.
3. **Biometric sensitivity**: embeddings are personal data — production use
   requires consent, retention limits and regional compliance (e.g. DPDP Act).
4. **Threshold tuning**: 0.45/0.60 suit the demo cohort; larger roll-outs
   should re-validate on real populations (ethnicity/lighting bias checks).

## 11. Future Work

- Real SMTP/portal credentials + scheduled sending on a server
- Public HTTPS deployment on a college domain
- InsightFace/YOLOv8 engine swap (interface already isolates the engine)
- Liveness detection; student photo self-enrollment with teacher approval
- Admin UI for PIN resets; per-parent email alerts

## 12. How to Run

```bash
bash scripts/setup_env.sh            # or use Docker (§9)
python app.py                        # → http://localhost:8000
python tests/test_face_engine.py     # 11 checks
python tests/test_web_flow.py        # 50 checks
python scripts/send_alerts.py --preview
```

Demo credentials — admin: `teacher@college.edu / teacher123` ·
teacher: `arjun@college.edu / teacher123` · student portal:
`ST001 + PIN 1234` (any demo student).

## Appendix A — Repository Layout

```
app.py                     Flask app (routes, HITL confirm, analytics, roles, portal)
config.py                  all thresholds & settings (env-overridable)
face_engine/               detector.py · encoder.py · recognizer.py
database/                  models.py · seed.py (idempotent + migrations)
reports.py · mailer.py     shared risk stats · email digest backends
templates/ · static/       UI (no CDN dependencies)
scripts/                   setup_env.sh · enroll_students.py · run_phase2_demo.py
                           stress_test.py · send_alerts.py
tests/                     test_face_engine.py · test_web_flow.py
docs/PROJECT_REPORT.md     this report
Dockerfile · docker-compose.yml · .dockerignore
```
