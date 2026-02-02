FROM python:3.11-slim

WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "app.bot"]
