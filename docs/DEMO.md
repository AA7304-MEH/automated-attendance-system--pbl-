# 🎬 Demo Script — PBL Evaluation (8–10 minutes)

Exact click path, what to say, and what to point at. All logins are seeded
automatically on first run.

**Setup before the audience arrives**

```bash
python app.py            # or: docker compose up
# open http://localhost:8000
```

Have two browser windows ready: the app, and `data/outputs/annotated_full.jpg`
(the annotated group photo) as a backup slide if WiFi dies.

---

## 1. Login (30 s) — `teacher@college.edu / teacher123`

**Say:** "The teacher is the only one who can change attendance. Every mark in
the system is traceable to a human decision."

## 2. Dashboard (30 s)

**Point at:** today's present count, your subjects, the 75% at-risk line.

**Say:** "One photo takes attendance for the whole class. Watch."

## 3. The AI pass (1 min)

Click **"Try the demo photo"** (or upload `data/uploads/classroom_demo.jpg`).

**Say:** "The AI detects every face, converts it to a 128-dimension face
signature, and compares it against all enrolled students."

## 4. ★ Verification page — the core of the project (3 min)

**Point at the three colours:**

- **Green (auto-approved):** distance ≤ 0.45 — "the AI is confident; these are
  pre-checked, the teacher can still uncheck."
- **Amber (needs review):** 0.45–0.60 — "this is Human-in-the-Loop: side-by-side
  comparison of the classroom face vs the registered photo. The teacher
  confirms — or corrects the dropdown. That correction is stored as
  method='manual', so we can audit when the AI was wrong."
- **Red (unknown):** nobody matched — "a stranger can never be marked present
  by the AI; only a human can assign them."

**Do live:** uncheck one green student. **Say:** "Even the AI's best guesses
are overrulable — the teacher is the final authority."

Click **💾 Confirm attendance**.

## 5. Session detail (30 s)

**Say:** "Every row records *how* it was marked: auto, review, manual — plus
the AI's confidence percentage and which teacher verified it."

## 6. Analytics (1 min)

**Point at:** overall donut, daily trend line with the red at-risk line,
per-student bars, per-subject breakdown. Download **Student summary CSV**.

**Say:** "Reports for the college office are one click, with AI confidence
included."

## 7. Alerts + email (1 min)

**Point at:** ST005 flagged red with trend arrow and worst subject.
Click **"Preview email"** — show the actual digest email.

**Say:** "Teachers get this digest daily at 8am via cron — the script ships
with the project."

## 8. Roles (1 min)

Logout → login as `arjun@college.edu / teacher123`.

**Say:** "Professor Nair only sees Machine Learning, his subject. Admin pages
refuse him with 403. Admins manage accounts and subject assignment."

## 9. Student portal (1 min)

Logout → **Student portal** → `ST005` + PIN `1234`.

**Say:** "Students check their own attendance any time — read-only, PIN
protected, and it warns them when they're below 75%."

## 10. Close (30 s)

**Say:** "61 automated tests pass — including honesty checks: a leave-one-out
test proves the engine rejects students it wasn't enrolled with, and a
stranger is never auto-approved. AI suggests; the teacher decides."

---

## Tricky questions you may get (with answers)

| Question | Answer |
|---|---|
| "What if two students look alike?" | Their distance lands in the amber band → teacher reviews side-by-side. Twins → teacher corrects → stored as manual override. |
| "Can someone hold up a photo to fake attendance?" | In this 2-D build, possibly — production adds liveness detection (blink/depth). Listed in the report's future work. |
| "What if the photo is blurry?" | Faces drop below detectability → they default to **absent**, and the teacher uses the 'also present' list. Nothing is ever wrongly auto-approved. |
| "Where are the real student photos?" | Demo uses AI-generated faces only. Real biometrics stay in a git-ignored local folder per the privacy design. |
| "Accuracy?" | Same-person matches measured at 0.19–0.26 distance (auto band). Un-enrolled student rejected at 0.726, stranger at 0.802 — no false positives in any probe. |
