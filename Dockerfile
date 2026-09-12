FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p instance

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "run:app"]
