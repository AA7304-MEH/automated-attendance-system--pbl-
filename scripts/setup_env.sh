#!/usr/bin/env bash
# Restore the Python environment (installed packages do NOT persist between
# sessions in this workspace — run this once at the start of each session).
set -e
cd "$(dirname "$0")/.."

need() { python3 -c "import $1" 2>/dev/null; }

if need dlib; then
  echo "dlib: present"
else
  echo "dlib: installing (prebuilt wheel if available)..."
  pip install -q cmake
  if ls wheels/dlib*.whl >/dev/null 2>&1; then
    pip install -q wheels/dlib*.whl
  else
    echo "(no stashed wheel found — trying prebuilt 'dlib-bin', then source)"
    if pip install -q dlib-bin 2>/dev/null; then
      pip wheel dlib-bin --no-deps -w wheels -q || true
    else
      echo "(compiling from source, this takes ~10 min)"
      pip install -q dlib
    fi
  fi
fi

# face_recognition's dependency resolver pulls the dlib SOURCE package (which
# can fail to build) — install it with --no-deps on top of the dlib we already have.
need face_recognition || pip install -q --no-deps face_recognition face_recognition_models
need click || pip install -q click
# face_recognition_models (2017) still imports pkg_resources, removed in setuptools>=81
python3 -c "import pkg_resources" 2>/dev/null || pip install -q "setuptools<81"
need flask || pip install -q flask flask-sqlalchemy flask-login

python3 - <<'PY'
import cv2, numpy, dlib, face_recognition, flask
print(f"✅ environment ready — dlib {dlib.__version__} | opencv {cv2.__version__} | numpy {numpy.__version__}")
PY
