# Deployment image for the Automated Student Attendance System.
# Build:  docker build -t autoattendance .
# Run:    docker run -p 8000:8000 -v $(pwd)/data:/app/data autoattendance
#
# Uses the same dependency strategy as scripts/setup_env.sh: dlib comes from
# the prebuilt dlib-bin wheel (no compiler needed) and face_recognition is
# installed --no-deps on top of it.
FROM python:3.11-slim

# opencv runtime libs (libGL etc. are not needed with opencv-python-headless,
# but libglib is still required by cv2)
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
      numpy opencv-python-headless pandas \
      flask flask-sqlalchemy flask-login gunicorn \
      "setuptools<81" dlib-bin \
 && pip install --no-cache-dir --no-deps face-recognition face_recognition_models click

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
# data/ is a volume: the SQLite DB, enrollment portraits and encodings persist
# across rebuilds. First boot auto-seeds the demo data and builds the pkl.
# Worker count via WEB_CONCURRENCY env var (default 1 — safe for 512MB free tier;
# set 2+ on paid plans). gunicorn has no native env support, hence sh -c.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:8000 --workers \"${WEB_CONCURRENCY:-1}\" --timeout 180 app:app"]
