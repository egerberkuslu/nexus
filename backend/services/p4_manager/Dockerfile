FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/
COPY services/p4_manager/ /app/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8010

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
