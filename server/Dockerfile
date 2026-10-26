FROM python:3.12-slim-bookworm

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV ASTRA_DB=/data/astra.db
VOLUME /data

EXPOSE 8765 8766

CMD ["python", "bridge.py", "--host", "0.0.0.0", "--port", "8765"]
