FROM python:3.10.16

WORKDIR /app

COPY requirements.txt .

RUN pip install psycopg2-binary

RUN pip install --no-cache-dir -r requirements.txt

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

