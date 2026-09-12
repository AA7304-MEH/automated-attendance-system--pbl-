"""Shared reporting logic (Phase 5): per-student stats + trend summaries.

Used by the alerts page, CSV exports and the email digest so every view of
"who is at risk" comes from exactly one implementation.
"""

from collections import defaultdict
from datetime import timedelta

from config import ATTENDANCE_THRESHOLD
from database.models import Attendance, Student, Subject, now_ist


def student_pct(rows):
    """rows: Attendance records for one student -> (pct, present, total)."""
    total = len(rows)
    present = sum(1 for r in rows if r.status == "Present")
    return (present / total * 100 if total else 0.0), present, total


def student_summary():
    """Per-active-student stats: overall %, last-7-day %, delta, worst subject.

    Returns a list sorted worst-first — the single source of truth for
    alerts / exports / email digests.
    """
    marks = Attendance.query.all()
    by_student = defaultdict(list)
    for m in marks:
        by_student[m.student_id].append(m)

    today = now_ist().date()
    week_start = today - timedelta(days=7)
    students = {s.id: s for s in Student.query.filter_by(active=True)}
    subjects = {s.id: s for s in Subject.query.all()}

    out = []
    for stu_id, rows in by_student.items():
        stu = students.get(stu_id)
        if not stu:
            continue
        pct, present, total = student_pct(rows)
        recent = [m for m in rows if m.date >= week_start]
        r_pct, r_present, r_total = student_pct(recent)

        per_subj = defaultdict(lambda: [0, 0])
        for m in rows:
            per_subj[m.subject_id][1] += 1
            if m.status == "Present":
                per_subj[m.subject_id][0] += 1
        worst = None
        for s_id, (p, t) in per_subj.items():
            if t >= 3 and (worst is None or p / t < worst[1]):
                worst = (subjects[s_id].code, p / t)

        out.append({
            "student": stu, "pct": pct, "present": present, "total": total,
            "recent_pct": r_pct, "recent_present": r_present, "recent_total": r_total,
            "delta": (r_pct - pct) if r_total else 0.0,
            "worst_subject": f"{worst[0]} ({worst[1] * 100:.0f}%)" if worst else None,
        })
    out.sort(key=lambda x: x["pct"])
    return out


def split_risk(summary):
    """summary -> (at_risk, borderline) using configured thresholds."""
    at_risk = [s for s in summary if s["pct"] < ATTENDANCE_THRESHOLD]
    borderline = [
        s for s in summary
        if ATTENDANCE_THRESHOLD <= s["pct"] < ATTENDANCE_THRESHOLD + 10.0
    ]
    return at_risk, borderline
