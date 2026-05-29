FROM python:3.11-slim

WORKDIR /app

COPY requirements-koyeb.txt .
RUN pip install --no-cache-dir -r requirements-koyeb.txt

COPY . .

RUN mkdir -p bot/uploads bot/vectorstore bot/database

CMD ["python", "main.py"]
