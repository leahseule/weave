FROM python:3.12-slim

WORKDIR /code

# ffmpeg: 25MB 초과 오디오를 조각내 전사할 때 사용. psycopg2-binary는 libpq 내장.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
