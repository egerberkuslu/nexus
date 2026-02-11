FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/
COPY services/vimemu_service/ /app/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 6001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6001"]
