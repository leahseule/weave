FROM python:3.12-slim

WORKDIR /code

# System deps kept minimal; psycopg2-binary ships its own libpq.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
